#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2009 Andreas Lang-Nevyjel
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
import os
import time
import commands
import server_command
import process_tools
import logging_tools
import pwd
import grp
import configfile
import ipvx_tools

class write_nameserver_config(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_config(["name_server", "name_slave"])
    def call_it(self, opt_dict, call_params):
        log_lines, sys_dict = process_tools.fetch_sysinfo("/")
        sys_version = sys_dict["version"]
        if sys_version.startswith("8") or sys_version == "sles8":
            named_dir = "/var/named"
        else:
            named_dir = "/var/lib/named"
        if not os.path.isdir(named_dir):
            ret_str = "error no named_dir %s" % (named_dir)
        else:
            act_conf_dict = configfile.read_global_config(call_params.dc, self.act_config_name.replace("%", ""))
            # get user/group id
            #print act_conf_dict.get("USER", "root")
            named_user, named_group = (act_conf_dict.get("USER", "root"),
                                       act_conf_dict.get("GROUP", "root"))
            try:
                named_uid = pwd.getpwnam(named_user)[2]
            except KeyError:
                named_uid = 0
            try:
                named_gid = grp.getgrnam(named_group)[2]
            except KeyError:
                named_gid = 0
            cf_lines = ["options {",
                        "  default-server localhost;",
                        "};",
                        "server localhost {",
                        "  key key1;",
                        "};",
                        "key key1 {",
                        "  algorithm hmac-md5;"]
            if act_conf_dict.has_key("SECRET"):
                cf_lines.append("  secret \"%s\" ;" % (act_conf_dict["SECRET"]))
            cf_lines.append("};")
            ncf_lines = ["options {",
                         "  directory \"%s\";\n" % (named_dir),
                         "  datasize default;",
                         "  stacksize default;",
                         "  coresize default;",
                         #"  files unlimited;",
                         "  auth-nxdomain no;"]
            forwarders = [act_conf_dict[x] for x in act_conf_dict.keys() if x.startswith("FORWARDER")]
            if len(forwarders):
                ncf_lines.append("  forwarders {\n%s\n  };" % ("\n".join(["    %s;" % (x) for x in forwarders if x])))
            ncf_lines.append("  listen-on {")
            server_idxs = [call_params.get_server_idx()]
            if self.server_idx != call_params.get_server_idx():
                server_idxs.append(self.server_idx)
            call_params.dc.execute("SELECT i.ip, n.netdevice_idx FROM netip i, netdevice n WHERE i.netdevice = n.netdevice_idx AND (%s)" % (" OR ".join(["n.device=%d" % (x) for x in server_idxs])))
            my_ips, my_netdev_idxs = ([], [])
            for db_rec in call_params.dc.fetchall():
                my_netdev_idxs.append(db_rec["netdevice_idx"])
                my_ips.append(db_rec["ip"])
                ncf_lines.append("    %s;" % (db_rec["ip"]))
            ncf_lines.extend(["  };",
                              "};",
                              "controls {",
                              "  inet * allow { any ; } keys { \"key1\"; };",
                              "};",
                              "key key1 {",
                              "  algorithm hmac-md5;"])
            if act_conf_dict.has_key("SECRET"):
                ncf_lines.append("  secret \"%s\" ;" % (act_conf_dict["SECRET"]))
            ncf_lines.extend(["};"])
            #ncf_lines.extend(["logging{",
                              #"  channel simple_log {",
                              #"    file \"/var/log/named/bind.log\" versions 3 size 5m;",
                              #"    severity warning;",
                              #"    print-time yes;",
                              #"    print-severity yes;",
                              #"    print-category yes;",
                              #"  };",
                              #"  category default{",
                              #"    simple_log;",
                              #"  };",
                              #"};"])
            ncf_lines.extend(["\nzone \".\" IN {",
                              "  type hint;",
                              "  file \"root.hint\";",
                              "};"])
            ncf_lines.extend(["\ninclude \"/etc/named.conf.include\";"])
            real_config_name = self.act_config_name.replace("%", "")
            other_conf = {"name_server" : "name_slave",
                          "name_slave"  : "name_server"}[real_config_name]
            # get peers
            sql_str = "SELECT i.ip, d.name FROM netip i INNER JOIN netdevice n INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN network nw INNER JOIN network_type nt INNER JOIN hopcount h INNER JOIN device d INNER JOIN device_group dg " + \
                      "LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND n.device=d.device_idx AND i.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND nt.identifier='p' AND " + \
                      "n.netdevice_idx=h.s_netdevice AND (%s) AND (d.device_idx=dc.device OR d2.device_idx=dc.device) AND dc.new_config=c.new_config_idx AND c.name='%s' AND i.netdevice=n.netdevice_idx ORDER BY h.value" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in my_netdev_idxs]), other_conf)
            call_params.dc.execute(sql_str)
            master_ips, slave_ips = ([], [])
            if real_config_name == "name_server":
                # get slaves
                slave_ips = [x["ip"] for x in call_params.dc.fetchall()]
                sub_dir = "master"
            elif real_config_name == "name_slave":
                # get masters
                master_ips = [x["ip"] for x in call_params.dc.fetchall()]
                sub_dir = "slave"
            #print master_ips, slave_ips
            call_params.dc.execute("SELECT n.network_idx, n.netmask, n.name, n.postfix, n.network, nt.identifier FROM network n, network_type nt WHERE n.network_type=nt.network_type_idx AND n.write_bind_config")
            nets = call_params.dc.fetchall()
            for net in nets:
                nw_ip   = ipvx_tools.ipv4(net["network"])
                nw_mask = ipvx_tools.ipv4(net["netmask"])
                nw_ip_parts, nw_mask_parts = (nw_ip.parts,
                                              nw_mask.parts)
                network_parts = 4
                while True:
                    if nw_mask_parts[-1]:
                        break
                    network_parts -= 1
                    nw_mask_parts.pop(-1)
                    nw_ip_parts.pop(-1)
                nw_flipped_parts = [value for value in nw_ip_parts]
                nw_flipped_parts.reverse()
                nw_flipped_ip = ".".join(["%d" % (value) for value in nw_flipped_parts])
                nw_ip = ".".join(["%d" % (value) for value in nw_ip_parts])
                nwname = net["name"]
                write_zone_file = 1
                for name, name2 in [(nwname, nwname),
                                    ("%s.in-addr.arpa" % (nw_flipped_ip), nw_ip)]:
                    ncf_lines.append("\nzone \"%s\" IN {" % (name))
                    zonefile_name = "%s.zone" % (name2)
                    if net["identifier"] == "l":
                        ncf_lines.extend(["  type master;",
                                          "  notify no;",
                                          "  allow-transfer { none; };"])
                    else:
                        if real_config_name == "name_server":
                            ncf_lines.append("  type master;")
                            if len(slave_ips):
                                ncf_lines.extend(["  notify yes;",
                                                  "  allow-transfer { %s; };" % ("; ".join(slave_ips)),
                                                  "  also-notify { %s; };\n" % ("; ".join(slave_ips))])
                            else:
                                ncf_lines.extend(["  notify no;",
                                                  "  allow-transfer { none; };",
                                                  "  allow-update { none; };"])
                        elif real_config_name == "name_slave":
                            zonefile_name = "slave/%s.zone" % (name2)
                            write_zone_file = 0
                            ncf_lines.extend(["  type slave;",
                                              "  allow-transfer { none; };",
                                              "  notify no;",
                                              "  masters { %s; };" % ("; ".join(master_ips))])
                    ncf_lines.extend(["  file \"%s/%s\";" % (sub_dir, zonefile_name),
                                      "};"])

                if write_zone_file:
                    timef = time.strftime("%Y%m%d%H", time.localtime(time.time()))

                    a_lines, b_lines = ([], [])
                    azname = "%s." % (nwname)
                    bzname = "%s.in-addr.arpa." % (nw_flipped_ip)
                    for lines, zname in [(a_lines, azname), (b_lines, bzname)]:
                        lines.extend(["$ORIGIN %s" % (zname),
                                      "$TTL 30M",
                                      "%s  IN SOA %s lang-nevyjel.%s. (" % (zname, nwname, nwname)])
                        for what in [timef, "1H", "15M", "1W", "30M"]:
                            lines.append("%s%s" % (" " * 10, what))
                        lines.extend(["%s)" % (" " * 5),
                                      "; NS and MX-records"])
                    a_form, b_form = (logging_tools.form_list(),
                                      logging_tools.form_list())
                    a_form.set_format_string(3, "s", "-", "; ")
                    b_form.set_format_string(3, "s", "-", "; ")
                    a_form.add_line([" ", "IN NS", "%s%s.%s." % (call_params.get_l_config()["SERVER_SHORT_NAME"], net["postfix"], net["name"]), ""])
                    b_form.add_line([" ", "IN NS", "%s%s.%s." % (call_params.get_l_config()["SERVER_SHORT_NAME"], net["postfix"], net["name"]), ""])
                    call_params.dc.execute("SELECT * FROM device_type")
                    for entry in call_params.dc.fetchall():
                        addstr = entry["description"]
                        if net["identifier"] == "l":
                            sel_str = " AND d.name='%s'" % (call_params.get_l_config()["SERVER_SHORT_NAME"])
                        else:
                            sel_str = ""
                        call_params.dc.execute("SELECT i.ip, d.name, i.alias, i.alias_excl, d.comment FROM netdevice n, device d, netip i, device_type dt WHERE dt.identifier=%%s AND d.device_type = dt.device_type_idx AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND i.network=%%s %s ORDER BY i.ip" % (sel_str),
                                               (entry["identifier"], net["network_idx"]))
                        rets = call_params.dc.fetchall()
                        if len(rets):
                            a_form.add_line("; %s %s" % (addstr,
                                                         logging_tools.get_plural("record", len(rets))))
                            b_form.add_line("; %s %s" % (addstr,
                                                         logging_tools.get_plural("record", len(rets))))
                            for ret in rets:
                                host_part = str(ipvx_tools.ipv4(ret["ip"]) & (~ ipvx_tools.ipv4(net["network"]))).split(".")
                                host_part.reverse()
                                for idx in range(network_parts):
                                    host_part.pop(-1)
                                fiand = ".".join(host_part)
                                out_names = []
                                if not (ret["alias"].strip() and ret["alias_excl"]):
                                    out_names.append("%s%s" % (ret["name"], net["postfix"]))
                                out_names.extend(ret["alias"].strip().split())
                                first = 1
                                for s_name in out_names:
                                    b_form.add_line([fiand, "IN PTR", "%s.%s." % (s_name, net["name"]), ret["comment"]])
                                    if first:
                                        first = 0
                                        f_name = s_name
                                        a_form.add_line([s_name, "IN A", ret["ip"], ret["comment"]])
                                    else:
                                        a_form.add_line([s_name, "CNAME", f_name, ret["comment"]])
                    a_lines.extend(str(a_form).split("\n"))
                    b_lines.extend(str(b_form).split("\n"))
                    afile_name = "%s/%s/%s.zone" % (named_dir, sub_dir, nwname)
                    bfile_name = "%s/%s/%s.zone" % (named_dir, sub_dir, nw_ip)
                    for name, lines in [(afile_name, a_lines), (bfile_name, b_lines)]:
                        file(name, "w").write("\n".join(lines + [""]))
                        os.chmod(name, 0600)
                        os.chown(name, named_uid, named_gid)
            cfile = "/etc/rndc.conf"
            ncname = "/etc/named.conf"
            file(ncname, "w").write("\n".join(ncf_lines + [""]))
            file(cfile, "w").write("\n".join(cf_lines + [""]))
            os.chmod(cfile, 0600)
            os.chmod(ncname, 0600)
            os.chown(ncname, named_uid, named_gid)
            cstat, cout = commands.getstatusoutput("/usr/sbin/rndc reload")
            if cstat:
                ret_str = "error wrote nameserver-config (%d networks), reloading gave :'%s'" % (len(nets), cout)
            else:
                ret_str = "ok wrote nameserver-config (%d networks) and successfully reloaded configuration" % (len(nets))
        return ret_str

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
