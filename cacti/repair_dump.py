#!/usr/bin/python-init -Ot

import sys
import datetime
import commands
import os
import os.path
import time

TMP_DIR = "/var/lib/rrd_repair"

def parse_ref(in_str):
    if len(in_str) != 12:
        print "Len Ref != 12 (%d)" % (len(in_str))
        sys.exit(0)
    return datetime.datetime(int(in_str[0:4]),
                             int(in_str[4:6]),
                             int(in_str[6:8]),
                             int(in_str[8:10]),
                             int(in_str[10:12]))
def main():
    if not os.path.isdir(TMP_DIR):
        os.mkdir(TMP_DIR)
    if len(sys.argv) != 6:
        print "Need filename new_filename start_repair and_repair start_ref (form YYYYMMDDHHMM)"
        sys.exit(0)
    f_name, new_f_name = sys.argv[1:3]
    bu_file = "%s/%s_%s" % (TMP_DIR, os.path.basename(f_name), time.ctime().replace(" ", "_").replace("__", "_"))
    print "Backup of %s is %s" % (f_name, bu_file)
    file(bu_file, "w").write(file(f_name, "r").read())
    # refs in form YYYYMMDDHHMM
    start_repair, end_repair = (parse_ref(sys.argv[3]), parse_ref(sys.argv[4]))
    print start_repair, end_repair
    start_ref = (parse_ref(sys.argv[5]))
    repair_length = end_repair - start_repair
    end_ref = start_ref + repair_length
    print "Repair length is %s" % (str(repair_length))
    dump_lines = commands.getoutput("/opt/rrdtool/bin/rrdtool dump %s" % (f_name)).split("\n")
    # generate repair
    rep_db = {}
    in_db, db_idx = (False, 0)
    k, d = ({}, {})
    for line in dump_lines:
        if line.lstrip().startswith("<database>"):
            print "db_start"
            in_db = True
            data_ok = False
            ref_dates, rep_dates = ({}, {})
        elif line.lstrip().startswith("</database>"):
            # repair
            print "Starting repair, length of ref_dates is %d, length of rep_dates is %d" % (len(ref_dates),
                                                                                             len(rep_dates))
            ref_keys = ref_dates.keys()
            ref_keys.sort()
            rep_keys = rep_dates.keys()
            rep_keys.sort()
            if ref_keys:
                if not k:
                    # calculate k and d
                    f0x0 = ref_dates[ref_keys[0]]
                    f0x1 = ref_dates[ref_keys[-1]]
                    f1x0 = rep_dates[rep_keys[0]]
                    f1x1 = rep_dates[rep_keys[-1]]
                    k[0] = ((f1x1[0] - f1x0[0]) - (f0x1[0] - f0x0[0])) / (rep_keys[0][0] - rep_keys[-1][0])
                    d[0] = f1x0[0] - f0x0[0]
                    k[1] = ((f1x1[1] - f1x0[1]) - (f0x1[1] - f0x0[1])) / (rep_keys[0][0] - rep_keys[-1][0])
                    d[1] = f1x0[1] - f0x0[1]
                # repair it
                if rep_keys:
                    s_second = rep_keys[0][0]
                    rep_db[db_idx] = {}
                    rf_idx = 0
                    for rep_second, rep_date in rep_keys:
                        sval = ref_dates[ref_keys[rf_idx]]
                        rf_idx += 1
                        full_key = (rep_second, rep_date)
                        new_val = (str(sval[0] - k[0] * (rep_second - s_second) + d[0]),
                                   str(sval[1] - k[1] * (rep_second - s_second) + d[1]))
                        rep_db[db_idx][full_key] = new_val
            db_idx += 1
            in_db = False
        elif in_db:
            vals = line.strip().split()
            act_date = datetime.datetime(int(vals[1][0:4]),
                                         int(vals[1][5:7]),
                                         int(vals[1][8:10]),
                                         int(vals[2][0:2]),
                                         int(vals[2][3:5]),
                                         int(vals[2][6:8]))
            if start_ref <= act_date and act_date <= end_ref:
                ref_dates[(int(vals[5]), act_date)] = (float(vals[8]), float(vals[10]))
            if start_repair <= act_date and act_date <= end_repair:
                rep_dates[(int(vals[5]), act_date)] = (float(vals[8]), float(vals[10]))
    # create new file
    new_file = file("%s.xml" % (new_f_name), "w")
    in_db, db_idx = (False, 0)
    for line in dump_lines:
        if line.lstrip().startswith("<database>"):
            in_db = True
        elif line.lstrip().startswith("</database>"):
            in_db = False
            db_idx += 1
        elif in_db:
            vals = line.strip().split()
            act_date = datetime.datetime(int(vals[1][0:4]),
                                         int(vals[1][5:7]),
                                         int(vals[1][8:10]),
                                         int(vals[2][0:2]),
                                         int(vals[2][3:5]),
                                         int(vals[2][6:8]))
            if start_repair <= act_date and act_date <= end_repair:
                vals[8], vals[10] = rep_db[db_idx][(int(vals[5]), act_date)]
                # trigger error if nan
                if vals[8] == "nan" or vals[10] == "nan":
                    print "*** Trying to insert nan at datetime %s, stopping" % (act_date)
                    sys.exit(0)
                line = " ".join(vals)
                #rep_dates[(int(vals[5]), act_date)] = (float(vals[8]), float(vals[10]))
        new_file.write("%s\n" % (line))
    new_file.close()
    rrd_file = "%s.rrd" % (new_f_name)
    if os.path.isfile(rrd_file):
        print "Removing %s ..." % (rrd_file)
        os.unlink(rrd_file)
    t_com = "/opt/rrdtool/bin/rrdtool restore %s.xml %s" % (new_f_name, rrd_file)
    print "Doing %s" % (t_com)
    act_stat, act_res = commands.getstatusoutput(t_com)
    if act_stat:
        print "error (%d): %s" % (act_stat, act_res)
    else:
        print "ok", act_res
    

if __name__ == "__main__":
    main()
    
