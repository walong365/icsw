# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-config-server
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
""" cluster-config-server, config generators """

from django.db.models import Q
from initat.cluster.backbone.models import device_variable, domain_tree_node, netdevice
from initat.cluster_config_server.config import global_config, GATEWAY_THRESHOLD
from initat.cluster_config_server.partition_setup import partition_setup
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
import base64
import commands
import logging_tools
import networkx
import os
import re
import tempfile

def do_uuid(conf):
    conf_dict = conf.conf_dict
    uuid_str = "urn:uuid:%s" % (conf_dict["device"].uuid)
    cdf_file = conf.add_file_object("/etc/sysconfig/cluster/.cluster_device_uuid")
    cdf_file.append(uuid_str)
    hm_uuid = conf.add_file_object("/etc/sysconfig/host-monitoring.d/0mq_id")
    hm_uuid.append(
        etree.tostring(
            E.bind_info(E.zmq_id(uuid_str, bind_address="*")),
            pretty_print=True,
            xml_declaration=True,
        )
    )

def do_nets(conf):
    conf_dict = conf.conf_dict
    sys_dict = conf_dict["system"]
    append_dict, dev_dict = ({}, {})
    write_order_list, macs_used, lu_table = ([], {}, {})
    for check_for_bootdevice in [False, True]:
        for cur_ip in conf_dict["node_if"]:
            if (not check_for_bootdevice and cur_ip.netdevice_id == conf_dict["device"].bootnetdevice_id) or (check_for_bootdevice and not cur_ip.netdevice_id == conf_dict["device"].bootnetdevice_id):
                if int(cur_ip.netdevice.macaddr.replace(":", ""), 16) != 0 and cur_ip.netdevice.macaddr.lower() in macs_used.keys():
                    print "*** error, macaddress %s on netdevice %s already used for netdevice %s" % (cur_ip.netdevice.macaddr, cur_ip.netdevice.devname, macs_used[cur_ip.netdevice.macaddr.lower()])
                else:
                    macs_used[cur_ip.netdevice.macaddr.lower()] = cur_ip.netdevice.devname
                    write_order_list.append(cur_ip.netdevice_id)
                    lu_table[cur_ip.netdevice_id] = cur_ip
    if sys_dict["vendor"] == "debian":
        glob_nf = conf.add_file_object("/etc/network/interfaces")
        auto_if = []
        for net_idx in write_order_list:
            net = lu_table[net_idx]
            auto_if.append(net["devname"])
        glob_nf += "auto %s" % (" ".join(auto_if))
        # get default gw
        _gw_source, def_ip, boot_dev, _boot_mac = get_default_gw(conf)
    for net_idx in write_order_list:
        cur_ip = lu_table[net_idx]
        cur_nd = cur_ip.netdevice
        cur_net = cur_ip.network
        cur_dtn = cur_ip.domain_tree_node
        if cur_dtn is None:
            cur_dtn = domain_tree_node.objects.get(Q(depth=0))
        if cur_nd.pk == conf_dict["device"].bootnetdevice_id:
            if sys_dict["vendor"] == "suse":
                new_co = conf.add_file_object("/etc/HOSTNAME")
                new_co += "%s%s.%s" % (conf_dict["host"], cur_dtn.node_postfix, cur_dtn.full_name)
            elif sys_dict["vendor"] == "debian":
                new_co = conf.add_file_object("/etc/hostname")
                new_co += "%s%s.%s" % (conf_dict["host"], cur_dtn.node_postfix, cur_dtn.full_name)
            else:
                new_co = conf.add_file_object("/etc/sysconfig/network", append=True)
                new_co += "HOSTNAME=%s" % (conf_dict["host"])
                new_co += "NETWORKING=yes"
        log_str = "netdevice %10s (mac %s)" % (cur_nd.devname, cur_nd.macaddr)
        if sys_dict["vendor"] == "suse":
            # suse-mode
            if ((sys_dict["version"] >= 9 and sys_dict["release"] > 0) or sys_dict["version"] > 9):
                act_filename = None
                if any([cur_nd.devname.startswith(cur_pf) for cur_pf in ["eth", "myri", "ib"]]):
                    mn = re.match("^(?P<devname>.+):(?P<virtual>\d+)$", cur_nd.devname)
                    if mn:
                        log_str += ", virtual of %s" % (mn.group("devname"))
                        append_dict.setdefault(mn.group("devname"), {})
                        append_dict[mn.group("devname")][mn.group("virtual")] = {
                            "BROADCAST" : cur_net.broadcast,
                            "IPADDR"    : cur_ip.ip,
                            "NETMASK"   : cur_net.netmask,
                            "NETWORK"   : cur_net.network}
                    else:
                        # FIXME; take netdevice even with zero macaddr
                        if int(cur_nd.macaddr.replace(":", ""), 16) != 0 or True:
                            dev_dict[cur_nd.devname] = cur_nd.macaddr
                            if sys_dict["vendor"] == "suse" and ((sys_dict["version"] == 10 and sys_dict["release"] == 3) or sys_dict["version"] > 10 or (sys_dict["version"], sys_dict["release"]) == (10, 10)):
                                # openSUSE 10.3, >= 11.0
                                if cur_nd.vlan_id:
                                    act_filename = "ifcfg-vlan%d" % (cur_nd.vlan_id)
                                else:
                                    act_filename = "ifcfg-%s" % (cur_nd.devname)
                            else:
                                act_filename = "ifcfg-eth-id-%s" % (cur_nd.macaddr)
                                if global_config["ADD_NETDEVICE_LINKS"]:
                                    conf.add_link_object("/etc/sysconfig/network/%s" % (act_filename), "/etc/sysconfig/network/ifcfg-%s" % (cur_nd.devname))
                        else:
                            log_str += ", ignoring (zero macaddress)"
                else:
                    act_filename = "ifcfg-%s" % (cur_nd.devname)
                if act_filename:
                    act_file = {
                        "BOOTPROTO" : "static",
                        "BROADCAST" : cur_net.broadcast,
                        "IPADDR"    : cur_ip.ip,
                        "NETMASK"   : cur_net.netmask,
                        "NETWORK"   : cur_net.network,
                        "STARTMODE" : "onboot"
                    }
                    if cur_nd.vlan_id:
                        if cur_nd.master_device:
                            act_file["ETHERDEVICE"] = cur_nd.master_device.devname
                            act_file["VLAN_ID"] = "%d" % (cur_nd.vlan_id)
                        else:
                            print "VLAN ID set but no master_device, skipping %s" % (cur_nd.devname)
                            act_filename = None
                    if not cur_nd.fake_macaddr:
                        pass
                    elif int(cur_nd.fake_macaddr.replace(":", ""), 16) != 0:
                        log_str += ", with fake_macaddr"
                        act_file["LLADDR"] = cur_nd.fake_macaddr
                        conf.add_link_object("/etc/sysconfig/network/ifcfg-eth-id-%s" % (cur_nd.fake_macaddr), act_filename)
                    if act_filename:
                        new_co = conf.add_file_object("/etc/sysconfig/network/%s" % (act_filename))
                        new_co += act_file
            else:
                act_filename = "ifcfg-%s" % (cur_nd.devname)
                act_file = {
                    "BOOTPROTO"     : "static",
                    "BROADCAST"     : cur_net.broadcast,
                    "IPADDR"        : cur_ip.ip,
                    "NETMASK"       : cur_net.netmask,
                    "NETWORK"       : cur_net.network,
                    "REMOTE_IPADDR" : "",
                    "STARTMODE"     : "onboot",
                    "WIRELESS"      : "no"}
                new_co = conf.add_file_object("/etc/sysconfig/network/%s" % (act_filename))
                new_co += act_file
        elif sys_dict["vendor"] == "debian":
            glob_nf += ""
            if net["devname"] == "lo":
                glob_nf += "iface %s inet loopback" % (cur_nd.devname)
            else:
                glob_nf += "iface %s inet static" % (cur_nd.devname)
                glob_nf += "      address %s" % (cur_ip.ip)
                glob_nf += "      netmask %s" % (cur_net.netmask)
                glob_nf += "    broadcast %s" % (cur_net.broadcast)
                if net["devname"] == boot_dev:
                    glob_nf += "      gateway %s" % (def_ip)
                if not cur_nd.fake_macaddr:
                    pass
                elif int(cur_nd.fake_macaddr.replace(":", ""), 16) != 0:
                    log_str += ", with fake_macaddr"
                    glob_nf += "    hwaddress ether %s" % (cur_nd.fake_macaddr)
        else:
            # redhat-mode
            act_filename = "ifcfg-%s" % (cur_nd.devname)
            if cur_nd.devname == "lo":
                d_file = "/etc/sysconfig/network-scripts/%s" % (act_filename)
            else:
                d_file = "/etc/sysconfig/network-scripts/%s" % (act_filename)
            new_co = conf.add_file_object(d_file)
            new_co += {
                "BOOTPROTO" : "static",
                "BROADCAST" : cur_net.broadcast,
                "IPADDR"    : cur_ip.ip,
                "NETMASK"   : cur_net.netmask,
                "NETWORK"   : cur_net.network,
                "DEVICE"    : cur_nd.devname,
                "ONBOOT"    : "yes"}
            if global_config["WRITE_REDHAT_HWADDR_ENTRY"]:
                if cur_nd.macaddr.replace(":", "").replace("0", "").strip():
                    new_co += {"HWADDR" : cur_nd.macaddr.lower()}
        # print log_str
    # handle virtual interfaces for Systems above SUSE 9.0
    for orig, virtuals in append_dict.iteritems():
        for virt, stuff in virtuals.iteritems():
            co = conf.add_file_object("/etc/sysconfig/network/ifcfg-eth-id-%s" % (dev_dict[orig]))
            co += {
                "BROADCAST_%s" % (virt) : stuff["BROADCAST"],
                "IPADDR_%s" % (virt)    : stuff["IPADDR"],
                "NETMASK_%s" % (virt)   : stuff["NETMASK"],
                "NETWORK_%s" % (virt)   : stuff["NETWORK"],
                "LABEL_%s" % (virt)     : virt}

def get_default_gw(conf):
    conf_dict = conf.conf_dict
    # how to get the correct gateway:
    # if all gw_pris < GATEWAY_THRESHOLD the server is the gateway
    # if any gw_pris >= GATEWAY_THRESHOLD the one with the highest gw_pri is taken
    gw_list = []
    for cur_ip in conf_dict["node_if"]:
        if cur_ip.netdevice.vlan_id:
            net_dev_name = "vlan%d" % (cur_ip.netdevice.vlan_id)
        else:
            net_dev_name = cur_ip.netdevice.devname
        gw_list.append((cur_ip.netdevice.pk, net_dev_name, cur_ip.network.gw_pri, cur_ip.network.gateway, cur_ip.netdevice.macaddr))
    # determine gw_pri
    def_ip, boot_dev, gw_source, boot_mac = ("", "", "<not set>", "")
    # any wg_pri above GATEWAY_THRESHOLD ?
    if gw_list:
        print "Possible gateways:"
        for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list:
            print " idx %3d, dev %6s, gw_pri %6d, gw_ip %15s, mac %s%s" % (
                netdev_idx,
                net_devname,
                gw_pri,
                gw_ip,
                net_mac,
                gw_pri > GATEWAY_THRESHOLD and "(*)" or "")
    max_gw_pri = max([gw_pri for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list])
    if  max_gw_pri > GATEWAY_THRESHOLD:
        gw_source = "network setting (gw_pri %d > %d)" % (max_gw_pri, GATEWAY_THRESHOLD)
        boot_dev, def_ip, boot_mac = [(net_devname, gw_ip, net_mac) for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list if gw_pri == max_gw_pri][0]
    elif "mother_server_ip" in conf_dict:
        # we use the bootserver_ip as gateway
        server_ip = conf_dict["mother_server_ip"]
        boot_dev, act_gw_pri, boot_mac = ([(net_devname, gw_pri, net_mac) for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list if netdev_idx == conf_dict["device"].bootnetdevice_id] + [("", 0, "")])[0]
        gw_source = "server address taken as ip from mother_server (gw_pri %d < %d and bootnetdevice_idx ok)" % (act_gw_pri, GATEWAY_THRESHOLD)
        def_ip = server_ip
    else:
        # nothing found
        pass
    return gw_source, def_ip, boot_dev, boot_mac

def do_routes(conf):
    conf_dict = conf.conf_dict
    sys_dict = conf_dict["system"]
    if sys_dict["vendor"] == "debian":
        pass
    else:
        if sys_dict["vendor"] == "suse":
            filename = "/etc/sysconfig/network/routes"
        else:
            filename = "/etc/sysconfig/static-routes"
        new_co = conf.add_file_object(filename)
        for cur_ip in conf_dict["node_if"]:
            cur_nd = cur_ip.netdevice
            cur_nw = cur_ip.network
            if cur_nd.vlan_id:
                net_dev_name = "vlan%d" % (cur_nd.vlan_id)
            else:
                net_dev_name = cur_nd.devname
            if cur_ip.network.network_type.identifier != "l":
                if sys_dict["vendor"] == "suse":
                    if sys_dict["vendor"] == "suse" and ((sys_dict["version"] == 10 and sys_dict["release"] == 3) or sys_dict["version"] > 10):
                        # openSUSE 10.3, >= 11.0
                        new_co += "%s 0.0.0.0 %s %s" % (cur_nw.network, cur_nw.netmask, net_dev_name)
                    else:
                        new_co += "%s 0.0.0.0 %s eth-id-%s" % (cur_nw.network, cur_nw.netmask, cur_nd.macaddr)
                elif sys_dict["vendor"] == "redhat" or sys_dict["vendor"].lower().startswith("centos"):
                    new_co += "any net %s netmask %s dev %s" % (cur_nw.network, cur_nw.netmask, cur_nd.devname)
        gw_source, def_ip, boot_dev, boot_mac = get_default_gw(conf)
        if def_ip:
            if sys_dict["vendor"] == "suse":
                new_co += "# from %s" % (gw_source)
                if sys_dict["vendor"] == "suse" and ((sys_dict["version"] == 10 and sys_dict["release"] == 3) or sys_dict["version"] > 10):
                    # openSUSE 10.3
                    new_co += "default %s - %s" % (def_ip, boot_dev)
                else:
                    new_co += "default %s - eth-id-%s" % (def_ip, boot_mac)
            elif sys_dict["vendor"] == "redhat" or sys_dict["vendor"].lower().startswith("centos"):
                # redhat-mode
                act_co = conf.add_file_object("/etc/sysconfig/network", append=True)
                act_co += "# from %s" % (gw_source)
                act_co += "GATEWAY=%s" % (def_ip)

def do_ssh(conf):
    conf_dict = conf.conf_dict
    # also used in fetch_ssh_keys
    ssh_types = [("rsa1", 1024), ("dsa", 1024), ("rsa", 1024), ("ecdsa", 521)]
    ssh_field_names = []
    for ssh_type, _size in ssh_types:
        ssh_field_names.extend(["ssh_host_%s_key" % (ssh_type), "ssh_host_%s_key_pub" % (ssh_type)])
    found_keys_dict = {key : None for key in ssh_field_names}
    for cur_var in device_variable.objects.filter(Q(device=conf_dict["device"]) & Q(name__in=ssh_field_names)):
        try:
            cur_val = base64.b64decode(cur_var.val_blob)
        except:
            pass
        else:
            found_keys_dict[cur_var.name] = cur_val
    print "found %s in database: %s" % (
        logging_tools.get_plural("key", len(found_keys_dict.keys())),
        ", ".join(sorted(found_keys_dict.keys())))
    new_keys = []
    for ssh_type, key_size in ssh_types:
        privfn = "ssh_host_%s_key" % (ssh_type)
        pubfn = "ssh_host_%s_key_pub" % (ssh_type)
        if not found_keys_dict[privfn] or not found_keys_dict[pubfn]:
            # delete previous versions
            device_variable.objects.filter(Q(device=conf_dict["device"]) & Q(name__in=[privfn, pubfn])).delete()
            print "Generating %s keys..." % (privfn)
            sshkn = tempfile.mktemp("sshgen")
            sshpn = "%s.pub" % (sshkn)
            if ssh_type:
                _cmd = "ssh-keygen -t {} -q -b {:d} -f {} -N ''".format(ssh_type, key_size, sshkn)
            else:
                _cmd = "ssh-keygen -q -b 1024 -f {} -N ''".format(sshkn)
            c_stat, c_out = commands.getstatusoutput(_cmd)
            if c_stat:
                print "error generating: {}".format(c_out)
            else:
                found_keys_dict[privfn] = file(sshkn, "rb").read()
                found_keys_dict[pubfn] = file(sshpn, "rb").read()
            try:
                os.unlink(sshkn)
                os.unlink(sshpn)
            except:
                pass
            new_keys.extend([privfn, pubfn])
    if new_keys:
        new_keys.sort()
        print "%s to create: %s" % (logging_tools.get_plural("key", len(new_keys)),
                                    ", ".join(new_keys))
        for new_key in new_keys:
            if found_keys_dict[new_key] is not None:
                new_dv = device_variable(
                    device=conf_dict["device"],
                    name=new_key,
                    var_type="b",
                    description="SSH key %s" % (new_key),
                    val_blob=base64.b64encode(found_keys_dict[new_key]))
                new_dv.save()
    for ssh_type, key_size in ssh_types:
        privfn = "ssh_host_%s_key" % (ssh_type)
        pubfn = "ssh_host_%s_key_pub" % (ssh_type)
        _pubfrn = "ssh_host_%s_key.pub" % (ssh_type)
        for var in [privfn, pubfn]:
            if found_keys_dict[var] is not None:
                new_co = conf.add_file_object("/etc/ssh/%s" % (var.replace("_pub", ".pub")))
                new_co.bin_append(found_keys_dict[var])
                if var == privfn:
                    new_co.mode = "0600"
        if ssh_type == "rsa1":
            for var in [privfn, pubfn]:
                new_co = conf.add_file_object("/etc/ssh/%s" % (var.replace("_rsa1", "").replace("_pub", ".pub")))
                new_co.bin_append(found_keys_dict[var])
                if var == privfn:
                    new_co.mode = "0600"

def do_fstab(conf):
    act_ps = partition_setup(conf)
    fstab_co = conf.add_file_object("/etc/fstab")
    fstab_co += act_ps.fstab

# generate /etc/hosts for nodes, including routing-info
def do_etc_hosts(conf):
    conf_dict = conf.conf_dict
    route_obj = conf.router_obj
    all_paths = []
    for cur_ip in conf_dict["node_if"]:
        all_paths.extend(networkx.shortest_path(route_obj.nx, cur_ip.netdevice_id, weight="weight").values())
    all_paths = sorted([route_obj.add_penalty(cur_path) for cur_path in all_paths])
    all_nds = set([cur_path[-1] for penalty, cur_path in all_paths])
    nd_lut = dict([(cur_nd.pk, cur_nd) for cur_nd in netdevice.objects.filter(Q(pk__in=all_nds)).select_related("device").prefetch_related("net_ip_set", "net_ip_set__network", "net_ip_set__domain_tree_node")])
    all_ips, ips_used = ([], set())
    for penalty, cur_path in all_paths:
        cur_nd = nd_lut[cur_path[-1]]
        for cur_ip in cur_nd.net_ip_set.all():
            if cur_ip.ip not in ips_used:
                # copy penalty value
                cur_ip.value = penalty
                ips_used.add(cur_ip.ip)
                # also check network identifiers ? FIXME
                all_ips.append((cur_nd, cur_ip))
    # ip addresses already written
    new_co = conf.add_file_object("/etc/hosts", append=True)
    # two iterations: at first the devices that match my local networks, than the rest
    tl_dtn = domain_tree_node.objects.get(Q(depth=0))
    loc_dict, max_len = ({}, 0)
    for cur_nd, cur_ip in all_ips:
        out_names = []
        cur_dtn = cur_ip.domain_tree_node or tl_dtn
        # override wrong settings for lo
        if not (cur_ip.alias.strip() and cur_ip.alias_excl):
            out_names.append("%s%s" % (cur_nd.device.name, cur_dtn.node_postfix))
        out_names.extend(cur_ip.alias.strip().split())
        if "localhost" in [entry.split(".")[0] for entry in out_names]:
            out_names = [entry for entry in out_names if entry.split(".")[0] == "localhost"]
        if cur_dtn.create_short_names:
            # also create short_names
            out_names = (" ".join(["%s.%s %s" % (entry, cur_dtn.full_name, entry) for entry in out_names])).split()
        else:
            # only print the long names
            out_names = ["%s.%s" % (entry, cur_dtn.full_name) for entry in out_names]
        loc_dict.setdefault(cur_ip.value, []).append([cur_ip.ip] + out_names)
        max_len = max(max_len, len(out_names) + 1)
    for pen, stuff in loc_dict.iteritems():
        for l_e in stuff:
            l_e.extend([""] * (max_len - len(l_e)) + ["#%d" % (pen)])
    for p_value in sorted(loc_dict.keys()):
        act_list = sorted(loc_dict[p_value])
        max_len = [0] * len(act_list[0])
        for line in act_list:
            max_len = [max(max_len[entry], len(line[entry])) for entry in range(len(max_len))]
        form_str = " ".join(["%%-%ds" % (part) for part in max_len])
        new_co += ["# penalty %d" % (p_value), ""] + [form_str % (tuple(entry)) for entry in act_list] + [""]

def do_hosts_equiv(conf):
    # no longer needed
    return
