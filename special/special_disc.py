
#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2010 Andreas Lang-Nevyjel, init.at
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
""" special task for configuring disk """

import sys
import pprint
import process_tools
import os.path

def handle(s_check, host, dc, build_proc, valid_ip, global_config=None, **kwargs):
    sc_array = []
    sql_str = "SELECT pt.name, pt.partition_table_idx, pt.valid, pd.*, p.*, ps.name AS psname FROM partition_table pt INNER JOIN device d LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx " + \
        "LEFT JOIN partition p ON p.partition_disc=pd.partition_disc_idx LEFT JOIN partition_fs ps ON ps.partition_fs_idx=p.partition_fs WHERE d.device_idx=%d AND d.act_partition_table=pt.partition_table_idx ORDER BY pd.priority DESC, p.pnum" % (host["device_idx"])
    dc.execute(sql_str)
    part_dev = host["partdev"]
    df_settings_dir = "%s/etc/df_settings" % (global_config["MD_BASEDIR"])
    df_sd_ok = os.path.isdir(df_settings_dir)
    build_proc.mach_log("Starting special disc for part_dev '%s', df_settings_dir is '%s' (%s)" % (part_dev or "NOT SET",
                                                                                                   df_settings_dir,
                                                                                                   "OK" if df_sd_ok else "not reachable"))
    first_disc = None
    all_parts = [x for x in dc.fetchall() if x["disc"] and x["mountpoint"]]
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
                build_proc.mach_log("Diskcheck on host %s requested an illegal partition %s -> skipped" % (host["name"], act_part), logging_tools.LOG_LEVEL_WARN)
                num_warning += 1
    # LVM-partitions
    sql_str = "SELECT lv.mountpoint, lv.warn_threshold, lv.crit_threshold, lv.name AS lvname, vg.name AS vgname FROM lvm_lv lv, lvm_vg vg, partition_table pt, device d WHERE lv.partition_table=pt.partition_table_idx AND d.act_partition_table=pt.partition_table_idx AND lv.lvm_vg=vg.lvm_vg_idx " + \
            "AND d.device_idx=%d ORDER BY lv.mountpoint" % (host["device_idx"])
    dc.execute(sql_str)
    for part_p in dc.fetchall():
        if part_p["mountpoint"]:
            warn_level, crit_level = (part_p.get("warn_threshold", 0),
                                      part_p.get("crit_threshold", 0))
            warn_level_str, crit_level_str = ("%d" % (warn_level) if warn_level else "",
                                              "%d" % (crit_level) if crit_level else "")
            part_list.append(("%s (LVM)" % (part_p["mountpoint"]), "/dev/mapper/%s-%s" % (part_p["vgname"], part_p["lvname"].replace("-", "--")),
                              warn_level_str, crit_level_str))
    # manual setting-dict for df
    set_dict = {}
    if df_sd_ok and os.path.isfile("%s/%s" % (df_settings_dir, host["name"])):
        lines = [line for line in file("%s/%s" % (df_settings_dir, host["name"]), "r").read().split("\n") if line.strip() and not line.strip().startswith("#")]
        for line in lines:
            parts = line.strip().split()
            if len(parts) == 3:
                if parts[0].startswith("/") and parts[1].isdigit() and parts[2].isdigit():
                    set_dict[parts[0]] = (int(parts[1]), int(parts[2]))
    for info_name, p_name, w_lev, c_lev in part_list:
        if p_name in set_dict:
            w_lev, c_lev = set_dict[p_name]
            build_proc.mach_log("    setting w/c to %d/%d" % (w_lev, c_lev))
            w_lev, c_lev = (str(w_lev) if w_lev > 0 else "", str(c_lev) if c_lev > 0 else "")
        build_proc.mach_log("  P: %-40s: %-40s (w: %-5s, c: %-5s)" % (info_name,
                                                                      p_name,
                                                                      w_lev or "N/S",
                                                                      c_lev or "N/S"))
        sc_array.append((info_name, [w_lev, c_lev, p_name]))
    return sc_array
            

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    
