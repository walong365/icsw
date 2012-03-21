#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2010,2012 Andreas Lang-Nevyjel, init.at
#
# this file is part of nagios-config-server
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
""" special tasks for generating md-config-server """

import sys
import pprint
import re
import logging_tools
import pyipc
import struct
import os
import process_tools
import server_command
from host_monitoring import ipc_comtools
import time

EXPECTED_FILE = "/etc/sysconfig/host-monitoring.d/openvpn_expected"

def parse_expected():
    ret_dict = {}
    if os.path.isfile(EXPECTED_FILE):
        in_field = open(EXPECTED_FILE, "r").read().split("\n")
        lines = [line.strip() for line in in_field if line.strip() and not line.strip().startswith("#")]
        for line in lines:
            if line.count("=") == 1:
                dev_name, dev_stuff = line.split("=", 1)
                dev_dict = {}
                ret_dict[dev_name.strip()] = dev_dict
                instances = dev_stuff.split()
                for instance in instances:
                    inst_parts = instance.split(":")
                    inst_dict = {}
                    dev_dict[inst_parts.pop(0)] = inst_dict
                    for inst_part in inst_parts:
                        c_parts = inst_part.split(",")
                        client_name = c_parts.pop(0)
                        inst_dict[client_name] = True
                        #inst_dict[client_name] = limits.nag_STATE_CRITICAL
                        #if c_parts and c_parts[0].lower() in ["w"]:
                        #    inst_dict[client_name] = limits.nag_STATE_WARNING
    return ret_dict

class special_base(object):
    def __init__(self, build_proc, dc, s_check, host, valid_ip, global_config):
        self.build_process = build_proc
        self.dc = dc
        self.s_check = s_check
        self.host = host
        self.valid_ip = valid_ip
        self.global_config = global_config
    def cleanup(self):
        self.dc = None
        self.build_process = None
        self.global_config = None
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.build_process.mach_log("[sc] %s" % (what), log_level)
    def __call__(self):
        s_time = time.time()
        cur_ret = self._call()
        e_time = time.time()
        self.log("took %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
        return cur_ret

class special_openvpn(special_base):
    def _call(self):
        return []
    
class special_disc_all(special_base):
    def _call(self):
        sc_array = []
        sc_array.append(("All partitions", ["",
                                            "",
                                            "ALL"]))
        return sc_array
        
class special_disc(special_base):
    def _call(self):
        sc_array = []
        sql_str = "SELECT pt.name, pt.partition_table_idx, pt.valid, pd.*, p.*, ps.name AS psname FROM partition_table pt INNER JOIN device d LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx " + \
            "LEFT JOIN partition p ON p.partition_disc=pd.partition_disc_idx LEFT JOIN partition_fs ps ON ps.partition_fs_idx=p.partition_fs WHERE d.device_idx=%d AND d.act_partition_table=pt.partition_table_idx ORDER BY pd.priority DESC, p.pnum" % (self.host["device_idx"])
        self.dc.execute(sql_str)
        part_dev = self.host["partdev"]
        df_settings_dir = "%s/etc/df_settings" % (self.global_config["MD_BASEDIR"])
        df_sd_ok = os.path.isdir(df_settings_dir)
        self.log("Starting special disc for part_dev '%s', df_settings_dir is '%s' (%s)" % (part_dev or "NOT SET",
                                                                                            df_settings_dir,
                                                                                            "OK" if df_sd_ok else "not reachable"))
        first_disc = None
        all_parts = [x for x in self.dc.fetchall() if x["disc"] and x["mountpoint"]]
        part_list = []
        for part_p in all_parts:
            if part_p["partition_hex"] == "82":
                # swap partiton
                pass
            else:
                act_disc, act_pnum = (part_p["disc"], part_p["pnum"])
                if not first_disc:
                    first_disc = act_disc
                if act_disc == first_disc and part_dev:
                    act_disc = part_dev
                part_pf = "p" if ("cciss" in act_disc or "ida" in act_disc) else ""
                act_part = "%s%s%d" % (act_disc, part_pf, act_pnum)
                # which partition to check
                check_part = act_part
                # check for lut_blob
                lut_blob = part_p.get("lut_blob", None)
                if lut_blob:
                    lut_blob = process_tools.net_to_sys(lut_blob)
                    if lut_blob:
                        if lut_blob.has_key("id"):
                            scsi_id = [act_id for act_id in lut_blob["id"] if act_id.startswith("scsi")]
                            if scsi_id:
                                scsi_id = scsi_id[0]
                                check_part = "/dev/disk/by-id/%s" % (scsi_id)
                if check_part.startswith("/"):
                    warn_level, crit_level = (part_p.get("warn_threshold", 0),
                                              part_p.get("crit_threshold", 0))
                    warn_level_str, crit_level_str = ("%d" % (warn_level) if warn_level else "",
                                                      "%d" % (crit_level) if crit_level else "")
                    part_list.append((part_p["mountpoint"],
                                      check_part, warn_level_str, crit_level_str))
                else:
                    self.log("Diskcheck on host %s requested an illegal partition %s -> skipped" % (self.host["name"], act_part), logging_tools.LOG_LEVEL_WARN)
        # LVM-partitions
        sql_str = "SELECT lv.mountpoint, lv.warn_threshold, lv.crit_threshold, lv.name AS lvname, vg.name AS vgname FROM lvm_lv lv, lvm_vg vg, partition_table pt, device d WHERE lv.partition_table=pt.partition_table_idx AND d.act_partition_table=pt.partition_table_idx AND lv.lvm_vg=vg.lvm_vg_idx " + \
                "AND d.device_idx=%d ORDER BY lv.mountpoint" % (self.host["device_idx"])
        self.dc.execute(sql_str)
        for part_p in self.dc.fetchall():
            if part_p["mountpoint"]:
                warn_level, crit_level = (part_p.get("warn_threshold", 0),
                                          part_p.get("crit_threshold", 0))
                warn_level_str, crit_level_str = ("%d" % (warn_level) if warn_level else "",
                                                  "%d" % (crit_level) if crit_level else "")
                part_list.append(("%s (LVM)" % (part_p["mountpoint"]), "/dev/mapper/%s-%s" % (part_p["vgname"], part_p["lvname"].replace("-", "--")),
                                  warn_level_str, crit_level_str))
        # manual setting-dict for df
        set_dict = {}
        if df_sd_ok and os.path.isfile("%s/%s" % (df_settings_dir, self.host["name"])):
            lines = [line for line in file("%s/%s" % (df_settings_dir, self.host["name"]), "r").read().split("\n") if line.strip() and not line.strip().startswith("#")]
            for line in lines:
                parts = line.strip().split()
                if len(parts) == 3:
                    if parts[0].startswith("/") and parts[1].isdigit() and parts[2].isdigit():
                        set_dict[parts[0]] = (int(parts[1]), int(parts[2]))
        for info_name, p_name, w_lev, c_lev in part_list:
            if p_name in set_dict:
                w_lev, c_lev = set_dict[p_name]
                self.log("    setting w/c to %d/%d" % (w_lev, c_lev))
                w_lev, c_lev = (str(w_lev) if w_lev > 0 else "", str(c_lev) if c_lev > 0 else "")
            self.log("  P: %-40s: %-40s (w: %-5s, c: %-5s)" % (info_name,
                                                                          p_name,
                                                                          w_lev or "N/S",
                                                                          c_lev or "N/S"))
            sc_array.append((info_name, [w_lev, c_lev, p_name]))
        return sc_array
    
class special_net(special_base):
    def _call(self):
        sc_array = []
        eth_check = re.match(".*ethtool.*", self.s_check["command_name"])
        self.log("Starting special net, eth_check is %s" % ("on" if eth_check else "off"))
        # never check duplex and stuff for a loopback-device
        if eth_check:
            if self.host["xen_guest"]:
                # no ethtool_checks for xen_guests
                net_check_sql_str = "(0)"
            else:
                net_check_sql_str = "(ns.check_via_ethtool=1 AND n.devname != 'lo')"
        else:
            if self.host["xen_guest"]:
                # no ethtool_checks for xen_guests
                net_check_sql_str = "(1)"
            else:
                net_check_sql_str = "(ns.check_via_ethtool=0 OR n.devname = 'lo')"
        self.dc.execute("SELECT n.devname, n.speed, ns.speed_bps, n.description, ns.full_duplex FROM netdevice n, netdevice_speed ns WHERE ns.netdevice_speed_idx=n.netdevice_speed AND n.device=%d AND %s" % (
            self.host["device_idx"],
            net_check_sql_str))
        all_net_devs = [x for x in self.dc.fetchall() if not re.match("^.*:\S+$", x["devname"])]
        for net_dev in all_net_devs:
            name_with_descr = "%s%s" % (net_dev["devname"],
                                        " (%s)" % (net_dev["description"]) if net_dev["description"] else "")
            eth_opts = []
            if eth_check:
                eth_opts.extend([net_dev["full_duplex"] and "full" or "half", "%d" % (net_dev["speed_bps"])])
            eth_opts.extend(["%.0f" % (net_dev["speed_bps"] * 0.9),
                             "%.0f" % (net_dev["speed_bps"] * 0.95)])
            eth_opts.append(net_dev["devname"])
            self.log(" - netdevice %s with %s: %s" % (name_with_descr,
                                                      logging_tools.get_plural("option", len(eth_opts) - 1),
                                                      ", ".join(eth_opts[:-1])))
            sc_array.append((name_with_descr, eth_opts))
        return sc_array

def handle(s_check, host, dc, build_proc, valid_ip, **kwargs):
    build_proc.mach_log("Starting special openvpn")
    exp_dict = parse_expected()
    if exp_dict.has_key(host["name"]):
        exp_dict = exp_dict[host["name"]]
    else:
        exp_dict = {}
    if not exp_dict:
        # no expected_dict found, try to get the actual config from the server
        srv_result = ipc_comtools.send_and_receive_zmq(valid_ip, "openvpn_status", server="collrelay", zmq_context=build_proc.zmq_context, port=2001)
        print unicode(srv_result)
        print "*" * 20
        try:
            res_ok, res_dict = ipc_comtools.send_and_receive(valid_ip, "openvpn_status", target_port=2001, decode=True)
        except:
            print "nogo"
            build_proc.mach_log("error getting open_status from %s: %s" % (valid_ip,
                                                                           process_tools.get_except_info()),
                                logging_tools.LOG_LEVEL_CRITICAL)
        else:
            print "go"
            if res_ok:
                build_proc.mach_log("error calling openvpn_status: %s" % (str(res_dict)),
                                    logging_tools.LOG_LEVEL_ERROR)
            else:
                # build exp_dict
                for inst_name in res_dict:
                    if res_dict[inst_name]["type"] == "server":
                        for c_name in res_dict[inst_name]["dict"]:
                            exp_dict.setdefault(inst_name, {})[c_name] = True
    sc_array = []
    for inst_name in sorted(exp_dict):
        for peer_name in sorted(exp_dict[inst_name]):
            sc_array.append(("OpenVPN peer %s on %s" % (peer_name, inst_name), [inst_name, peer_name]))
    if not sc_array:
        sc_array.append(("OpenVPN", ["ALL", "ALL"]))
    return sc_array

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    