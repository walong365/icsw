#!/usr/bin/python -Otu
#
# Copyright (C) 2007,2008,2011,2012 Andreas Lang-Nevyjel
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

import sys
import cs_base_class
import process_tools
import os
import array
import ipvx_tools
import pprint
import logging_tools
import server_command
import cluster_location
from django.db.models import Q
from init.cluster.backbone.models import net_ip, netdevice, device, device_variable, hopcount, device_group

SSH_KNOWN_HOSTS_FILENAME = "/etc/ssh/ssh_known_hosts"
ETC_HOSTS_FILENAME       = "/etc/hosts"

class write_etc_hosts(cs_base_class.server_com):
    class Meta:
        needed_configs = ["auto_etc_hosts"]
    def _call(self):
        file_list = []
        server_idxs = [self.server_idx]
        # get additional idx if host is virtual server
        #is_server, serv_idx, server_type, server_str, config_idx, real_server_name = cluster_location.is_server(self.dc, self.Meta.actual_configs[0], True, False)
        is_server, serv_idx, server_type, server_str, config_idx, real_server_name = cluster_location.is_server("server", True, False, dc=self.dc)
        if is_server and serv_idx != self.server_idx:
            server_idxs.append(serv_idx)
        # recognize for which devices i am responsible
        dev_r = cluster_location.device_recognition(dc=self.dc)
        server_idxs = list(set(server_idxs) | set(dev_r.device_dict.keys()))
        # get all peers to local machine and local netdevices
        #print "srv", server_idxs
        my_idxs = netdevice.objects.filter(Q(device__in=server_idxs)).values_list("pk", flat=True)
        #print "net", my_idxs
        # ref_table
        ref_table = dict([((cur_entry.s_netdevice_id, cur_entry.d_netdevice_id), cur_entry.value) for cur_entry in hopcount.objects.filter(Q(s_netdevice__in=my_idxs) | Q(d_netdevice__in=my_idxs))])
        #pprint.pprint(ref_table)
        #self.dc.execute("SELECT n.netdevice_idx FROM netdevice n WHERE (%s)" % (" OR ".join(["n.device=%d" % (srv_idx) for srv_idx in server_idxs])))
        #my_idxs = [db_rec["netdevice_idx"] for db_rec in self.dc.fetchall()]
        t_devs = net_ip.objects.filter(Q(netdevice__hopcount_s_netdevice__d_netdevice__in=my_idxs)).select_related("netdevice__device", "network__network_type").order_by(
            "netdevice__hopcount_s_netdevice__value", "netdevice__device__name", "ip"
        )
        all_hosts = list(t_devs)
##        sql_str = "SELECT DISTINCT d.name, i.ip, i.alias, i.alias_excl, nw.network_idx, n.netdevice_idx, n.devname, nt.identifier, nw.name AS domain_name, nw.postfix, nw.short_names, h.value FROM " + \
##                  "device d, netip i, netdevice n, network nw, network_type nt, hopcount h WHERE nt.network_type_idx=nw.network_type AND i.network=nw.network_idx AND n.device=d.device_idx AND " + \
##                  "i.netdevice=n.netdevice_idx AND n.netdevice_idx=h.s_netdevice AND (%s) ORDER BY h.value, d.name, i.ip, nw.postfix" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in my_idxs]))
##        self.dc.execute(sql_str)
##        all_hosts = [list(self.dc.fetchall())]
        # self-references
        my_devs = net_ip.objects.filter(Q(netdevice__hopcount_s_netdevice__d_netdevice__in=my_idxs) & Q(netdevice__device__in=server_idxs)).select_related("netdevice__device", "network__network_type").order_by(
            "netdevice__hopcount_s_netdevice__value", "netdevice__device__name", "ip"
        )
##        sql_str = "SELECT DISTINCT d.name, i.ip, i.alias, i.alias_excl, nw.network_idx, n.netdevice_idx, n.devname, nt.identifier, nw.name AS domain_name, nw.postfix, nw.short_names, n.penalty AS value FROM " + \
##                  "device d, netip i, netdevice n, network nw, network_type nt WHERE nt.network_type_idx=nw.network_type AND i.network=nw.network_idx AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND " + \
##                  "d.device_idx=%d ORDER BY d.name, i.ip, nw.postfix" % (self.server_idx)
##        self.dc.execute(sql_str)
        all_hosts.extend(list(my_devs))
        # fetch key-information
        ssh_vars = device_variable.objects.filter(Q(name="ssh_host_rsa_key_pub")).select_related("device")
        #sql_str = "SELECT DISTINCT d.name, dv.name AS dvname, dv.val_blob FROM device d LEFT JOIN device_variable dv ON dv.device=d.device_idx WHERE dv.name='ssh_host_rsa_key_pub'"
        #self.dc.execute(sql_str)
        rsa_key_dict = {}
        for db_rec in ssh_vars:
            print "* ssh_var *", db_rec
            if db_rec["val_blob"] and db_rec["dvname"] == "ssh_host_rsa_key_pub":
                if type(db_rec["val_blob"]) == type(array.array("b")):
                    key_str = db_rec["val_blob"].tostring().split()
                else:
                    key_str = db_rec["val_blob"].split()
                rsa_key_dict[db_rec["name"]] = " ".join(key_str)
        # read pre/post lines from /etc/hosts
        pre_host_lines, post_host_lines = ([], [])
        # parse pre/post host_lines
        try:
            host_lines = [line.strip() for line in file(ETC_HOSTS_FILENAME, "r").read().split("\n")]
        except:
            self.log("error reading / parsing %s: %s" % (ETC_HOSTS_FILENAME,
                                                         process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            mode, any_modes_found = (0, False)
            for line in host_lines:
                if line.lower().startswith("### aeh-start-pre"):
                    mode, any_modes_found = (1, True)
                elif line.lower().startswith("### aeh-start-post"):
                    mode, any_modes_found = (2, True)
                elif line.lower().startswith("### aeh-end"):
                    mode, any_modes_found = (0, True)
                else:
                    if mode == 1:
                        pre_host_lines.append(line)
                    elif mode == 2:
                        post_host_lines.append(line)
            if not any_modes_found:
                self.log("no ### aeh-.* stuff found in %s, copying to %s.orig" % (
                    ETC_HOSTS_FILENAME, ETC_HOSTS_FILENAME))
                try:
                    pass
                    #file("%s.orig" % (ETC_HOSTS_FILENAME), "w").write("\n".join(host_lines + [""]))
                except:
                    self.log("error writing %s.orig: %s" % (
                        ETC_HOSTS_FILENAME,
                        process_tools.get_except_info()))
        # mapping from device_name to all names for ssh_host_keys
        name_dict = {}
        # ip dictionary
        ip_dict = {}
        # build dict, ip->[list of hosts]
        for host in all_hosts:
            # get names
            host_names = []
            if not (host.alias.strip() and host.alias_excl):
                host_names.append("%s%s" % (host.netdevice.device.name, host.network.postfix))
            host_names.extend(host.alias.strip().split())
            if "localhost" in [x.split(".")[0] for x in host_names]:
                host_names = [host_name for host_name in host_names if host_name.split(".")[0] == "localhost"]
            if host.network.short_names:
                # also print short_names
                out_names = (" ".join(["%s.%s %s" % (host_name, host.network.name, host_name) for host_name in host_names if not host_name.count(".")])).split()
            else:
                # only print the long names
                out_names = ["%s.%s" % (host_name, host.network.name) for host_name in host_names if not host_name.count(".")]
            # add names with dot
            out_names.extend([host_name for host_name in host_names if host_name.count(".")])
            # name_dict without localhost
            name_dict.setdefault(host.netdevice.device.name, []).extend([out_name for out_name in out_names if out_name not in name_dict[host.netdevice.device.name] and not out_name.startswith("localhost")])
            ip_dict.setdefault(host.ip, [])
            if out_names not in [x[1] for x in ip_dict[host.ip]]:
                #print ref_table[(host.netdevice.hopcount_s_netdevice_id.value,
                #                 host.netdevice.hopcount_d_netdevice_id.value)]
                # FIXME, we have to find a way to get the hopcount value
                ip_dict[host.ip].append((1, out_names))
        # out_list
        loc_dict = {}
        for ip, h_list in ip_dict.iteritems():
            all_values = sorted([x[0] for x in h_list])
            min_value = all_values[0]
            out_names = []
            for val in all_values:
                for act_val, act_list in [(x_value, x_list) for x_value, x_list in h_list if x_value == val]:
                    out_names.extend([value for value in act_list if value not in out_names])
            #print min_value, ip, out_names
            loc_dict.setdefault(min_value, []).append([ipvx_tools.ipv4(ip)] + out_names)
        pen_list = sorted(loc_dict.keys())
        out_file = []
        for pen_value in pen_list:
            act_out_list = logging_tools.form_list()
            for entry in sorted(loc_dict[pen_value]):
                act_out_list.add_line([entry[0]] + entry[1:])
            host_lines = str(act_out_list).split("\n")
            out_file.extend(["# penalty %d, %s" % (pen_value,
                                                   logging_tools.get_plural("host entry", len(host_lines))), ""] + host_lines + [""])
        group_dir = "/usr/local/etc/group"
        if not os.path.isdir(group_dir):
            try:
                os.makedirs(group_dir)
            except:
                pass
        if os.path.isdir(group_dir):
            # remove old files
            for file_name in os.listdir(group_dir):
                try:
                    os.unlink(os.path.join(group_dir, file_name))
                except:
                    pass
            # get all devices with netips
            all_devs = device.objects.filter(Q(netdevice__net_ip__ip__contains=".")).values_list("name", "device_group__name").order_by("device_group__name", "name")
##            print all_devs
##            self.dc.execute("SELECT DISTINCT d.name, dg.name AS dgname FROM device d, device_group dg, netdevice n, netip i WHERE dg.device_group_idx=d.device_group AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx ORDER BY dg.name, d.name")
##            ddg_dict, all_names, all_nodes = ({}, [], [])
##            for db_rec in self.dc.fetchall():
##                ddg_dict.setdefault(db_rec["dgname"], []).append(db_rec["name"])
##                all_names.append(db_rec["name"])
            # FIXME
            if False:
                self.dc.execute("SELECT DISTINCT d.name, dg.name AS dgname, c.name FROM device d, device_group dg, device_config dc, new_config c WHERE (dc.device=d.device_idx OR dc.device=dg.device) AND c.new_config_idx=dc.new_config AND c.name LIKE('node%') AND dg.device_group_idx=d.device_group ORDER BY dg.name, d.name")
                ddg_dict["all_names"] = all_names
                ddg_dict["all_nodes"] = [x["name"] for x in self.dc.fetchall() if x["name"] in all_names]
                for dg_name, dg_hosts in ddg_dict.iteritems():
                    dg_hosts.sort()
                    try:
                        file("%s/%s" % (group_dir, dg_name), "w").write("\n".join(dg_hosts + [""]))
                    except:
                        pass
        #outhandle.seek(0, 0)
        file_list.append(ETC_HOSTS_FILENAME)
        file(ETC_HOSTS_FILENAME, "w+").write("\n".join(["### AEH-START-PRE insert pre-host lines below"] + pre_host_lines + ["### AEH-END-PRE insert pre-host lines above", ""] +
                                                       out_file +
                                                       ["", "### AEH-START-POST insert post-host lines below"] + post_host_lines + ["### AEH-END-POST insert post-host lines above", ""]))
        # write known_hosts_file
        if os.path.isdir(os.path.dirname(SSH_KNOWN_HOSTS_FILENAME)):
            skh_f = file(SSH_KNOWN_HOSTS_FILENAME, "w")
            for ssh_key_node in sorted(rsa_key_dict.keys()):
                skh_f.write("%s %s\n" % (",".join(name_dict.get(ssh_key_node, [ssh_key_node])), rsa_key_dict[ssh_key_node]))
            skh_f.close()
            file_list.append(SSH_KNOWN_HOSTS_FILENAME)
        #outhandle.close()
        # FIXME
        if False:
            for act_file, restr in [("/etc/nodenames", "c.name LIKE ('node%')"), ("/usr/local/etc/machines.list", "c.name LIKE('node%')"), ("/etc/clusternames", "1")]:
                act_dirname = os.path.dirname(act_file)
                if os.path.isdir(act_dirname):
                    file_list.append(act_file)
                    tf = file(act_file, "w+")
                    self.dc.execute("SELECT DISTINCT d.name FROM device d INNER JOIN device_type dt INNER JOIN new_config c INNER JOIN device_config dc INNER JOIN device_group dg LEFT JOIN " + \
                                           "device d2 ON d2.device_idx=dg.device WHERE dg.device_group_idx=d.device_group AND dt.identifier='H' AND dt.device_type_idx=d.device_type AND dc.new_config=c.new_config_idx AND " + \
                                           "(d2.device_idx=dc.device OR d.device_idx=dc.device) AND %s ORDER BY dg.name, d.name" % (restr))
                    for entry in self.dc.fetchall():
                        tf.write("%s\n" % (entry["name"]))
                    tf.close()
                else:
                    self.log("Error: directory '%s' not found" % (act_dirname))
        self.srv_com["result"].attrib.update({
            "reply" : "ok wrote %s" % (", ".join(sorted(file_list))),
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
