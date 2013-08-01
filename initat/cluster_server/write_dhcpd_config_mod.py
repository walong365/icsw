#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2008,2012,2013 Andreas Lang-Nevyjel
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

import config_tools
import cs_base_class
import pprint
import process_tools
import os
import server_command
import sys
from django.db.models import Q
from initat.cluster.backbone.models import net_ip, \
     network
from initat.cluster_server.config import global_config

class write_dhcpd_config(cs_base_class.server_com):
    class Meta:
        needed_configs = ["mother_server"]
        needed_option_keys = ["authoritative"]
    def _call(self, cur_inst):
        my_c = config_tools.server_check(server_type="mother_server")
        boot_ips = my_c.identifier_ip_lut.get("b", [])
        if len(boot_ips) > 1:
            cur_inst.srv_com["result"].attrib.update({
                "reply" : "error more than one boot-net found for '%s'" % (global_config["SERVER_SHORT_NAME"]),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        elif not boot_ips:
            cur_inst.srv_com["result"].attrib.update({
                "reply" : "error no boot-net found for '%s'" % (global_config["SERVER_SHORT_NAME"]),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            boot_ip = boot_ips[0]
            boot_net = boot_ip.network
            add_nets = list(network.objects.filter(Q(net_ip__netdevice__device=my_c.effective_device) &
                                                   Q(network_type__identifier__in=["s", "p", "o"])))
            if os.path.isdir("/etc/dhp3"):
                dhcpd_f = file("/etc/dhcp3/dhcpd.conf", "w")
            else:
                dhcpd_f = file("/etc/dhcpd.conf", "w")
            dhcpd_f.write("ddns-update-style none;\n")
            dhcpd_f.write("omapi-port 7911;\n")
            dhcpd_f.write("ddns-domainname \"%s\";\n" % (global_config["SERVER_SHORT_NAME"]))
            dhcpd_f.write("allow booting;\nallow bootp;\n\n")
            if cur_inst.srv_com["server_key:authoritative"].text.lower() in ["1", "true", "yes"]:
                dhcpd_f.write("authoritative;\n")
            # get gateway and domain-servers for the various nets
            gw_pri, gateway = (-10000, "0.0.0.0")
            cur_dc = config_tools.device_with_config("%server%")
            found_dict = {}
            for act_net in [boot_net] + add_nets:
                if act_net.gw_pri > gw_pri:
                    gw_pri, gateway = (act_net.gw_pri, act_net.gateway)
                
                for key, configs, add_dict in [("domain-name-servers", ["name_server", "name_slave"], {}),
                                               ("ntp-servers", ["xntp_server"], {}),
                                               ("nis-servers", ["yp_server"], {"domainname" : "nis-domain"})]:
##                    dc.execute("SELECT d.name, i.ip FROM device d INNER JOIN netip i INNER JOIN netdevice n INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN " + \
##                                           "device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND n.device = d.device_idx AND i.netdevice=n.netdevice_idx AND " + \
##                                           "i.network=%d AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND dc.new_config=c.new_config_idx AND (%s)" % (act_net["network_idx"], " OR ".join(["c.name='%s'" % (x) for x in configs])))
                    found_confs = set(cur_dc.keys()) & set(configs)
                    if found_confs:
                        # some configs found
                        for found_conf in found_confs:
                            for cur_srv in cur_dc[found_conf]:
                                match_list = [cur_ip for cur_ip in cur_srv.ip_list if cur_ip.network.pk == act_net.pk]
                                if match_list:
                                    # FIXME: honor add_dict
                                    #print cur_srv.config.config_str_set.all()
##                        for sql_key, dhcp_key in add_dict.iteritems():
##                            for tname in ["int", "str"]:
##                                sql_str = "SELECT cs.value FROM config_%s cs INNER JOIN new_config c INNER JOIN device_config dc INNER JOIN device d INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND cs.name='%s' AND cs.new_config=c.new_config_idx AND
## (%s) AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND (%s)" % (tname, sql_key, " OR ".join(["c.name='%s'" % (x) for x in configs]), " OR ".join(["d.name='%s'" % (x) for x in [y[1] for y in hosts]]))
##                                dc.execute(sql_str)
##                                if dc.rowcount:
##                                    opts[dhcp_key] = dc.fetchone()["value"]
                                    found_dict.setdefault(act_net.pk, {}).setdefault(key, []).append((cur_srv.device, match_list))
            #pprint.pprint(found_dict)
##                    if dc.rowcount:
##                        hosts, opts = ([(x["ip"], x["name"]) for x in dc.fetchall()], {})
##                        act_net[key] = {"hosts" : hosts, "opts" : opts}
                #act_net["dns"] = 
            dhcpd_f.write("shared-network %s {\n" % (global_config["SERVER_SHORT_NAME"]))
            dhcpd_f.write("  option routers %s;\n" % (gateway))
            for act_net in [boot_net] + add_nets:
                dhcpd_f.write("  subnet %s netmask %s {\n" % (act_net.network,
                                                              act_net.netmask))
                if act_net.network_type.identifier == "b":
                    dhcpd_f.write("    authoritative ;\n")
                dhcpd_f.write("    next-server %s;\n" % (my_c.identifier_ip_lut[act_net.network_type.identifier][0].ip))
                local_found_dict = found_dict.get(act_net.pk, {})
                for key in ["domain-name-servers", "ntp-servers", "nis-servers"]:
                    if key in local_found_dict:
                        dhcpd_f.write("    option %s %s;\n" % (key, ", ".join(["%s" % (cur_dev.name) for cur_dev, ip_list in local_found_dict[key]])))
                        # FIXME
                        #for o_key, o_value in act_net[key]["opts"].iteritems():
                        #    dhcpd_f.write("    option %s %s;\n" % (o_key, o_value))
                dhcpd_f.write("    server-identifier %s;\n" % (my_c.identifier_ip_lut[act_net.network_type.identifier][0].ip))
                dhcpd_f.write("    option domain-name \"%s\";\n" % (act_net.name))
                dhcpd_f.write("  }\n")
            dhcpd_f.write("}\n")
            # create netbotz-dhcp entries
            nb_devs = net_ip.objects.filter(Q(netdevice__device__device_type__identifier="NB") & Q(netdevice__device__boot_server=my_c.effective_device))
            if len(nb_devs):
                dhcpd_f.write("\ngroup netbotz {\n")
                for netbotz in nb_devs:
                    dhcpd_f.write("  host %s {\n    hardware ethernet %s;\n    fixed-address %s;\n  }\n" % (
                        netbotz.netdevice.device.name,
                        netbotz.netdevice.macaddr,
                        netbotz.ip))
                dhcpd_f.write("}\n")
            dhcpd_f.close()
            ret_state = None
            for s_name in ["dhcp3-server", "dhcpd"]:
                if os.path.isfile("/etc/init.d/%s" % (s_name)):
                    cstat, log_f = process_tools.submit_at_command("/etc/init.d/%s restart" % (s_name), 1)
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
            cur_inst.srv_com["result"].attrib.update({
                "reply" : ret_str,
                "state" : "%d" % (ret_state)})
            
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
