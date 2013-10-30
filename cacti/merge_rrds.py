#!/usr/bin/python-init -Ot

import sys
import datetime
import commands
import os
import os.path
import time

rra_dir = "/var/www/html/cacti/rra"
src_file = "vix_iec_vixtrafficin_1097.rrd"
dst_file_name = "/tmp/new.xml"
dst_file_rrd_name = "/tmp/new.rrd"
ref_time = time.mktime((2007, 9, 4, 16, 0, 0, 0, 0, 0))

class sum_data_obj(object):
    def __init__(self):
        self.__times = []
        self.__times_set = set()
        self.__data = {}
    def feed_data(self, in_data):
        print "feed start ... ",
        a_t, a_d = (self.__times_set, self.__data)
        for act_time, value in in_data.iteritems():
            if value[0] and value[1]:
                if act_time in a_t:
                    act_v0, act_v1 = a_d[act_time]
                    act_v0 += value[0]
                    act_v1 += value[1]
                    a_d[act_time] = (act_v0, act_v1)
                else:
                    a_t.add(act_time)
                    a_d[act_time] = value
        print "feed ok"
        self.__times = [x for x in self.__times_set]
        self.__times.sort()
        self.__min_time, self.__max_time = (min(self.__times), max(self.__times))
    def get_num(self, act_secs):
        if act_secs < self.__min_time:
            return self.__data[self.__min_time]
        elif act_secs > self.__max_time:
            return self.__data[self.__max_time]
        elif act_secs in self.__times:
            return self.__data[act_secs]
        else:
            min_time = 0
            for max_time in self.__times:
                if min_time < act_secs and max_time > act_secs:
                    break
                min_time = max_time
            return self._diff(min_time, act_secs, max_time, 0), self._diff(min_time, act_secs, max_time, 1)
    def _diff(self, x0, x, x1, idx):
        v0, v1 = (self.__data[x0][idx],
                  self.__data[x1][idx])
        if v0 is not None and v1 is not None:
            return v0 + (v1 - v0) / float(x1 - x0) * float(x - x0)
        else:
            return None
        
class rrd_file(object):
    def __init__(self, name):
        self.name = name
        self.lines = commands.getoutput("/opt/rrdtool/bin/rrdtool dump %s" % (self.name)).split("\n")
        if len(self.lines) > 10:
            self.ok = True
        else:
            self.ok = False
    def _parse(self, sum_data):
        self.__data = {}
        in_db = False
        for line in self.lines:
            if line.lstrip().startswith("<database>"):
                in_db = True
                ref_dates, rep_dates = ({}, {})
            elif line.lstrip().startswith("</database>"):
                in_db = False
            elif line.lstrip().startswith("<lastupdate>"):
                self.last_update = int(line.strip().split()[1])
            else:
                if in_db:
                    vals = line.strip().split()
                    try:
                        v0, v1 = (vals[8], vals[10])
                    except:
                        pass
                    else:
                        try:
                            if v0.lower() == "nan":
                                v0 = 0.0
                            else:
                                v0 = float(v0)
                        except:
                            v0 = 0.0
                        try:
                            if v1.lower() == "nan":
                                v1 = 0.0
                            else:
                                v1 = float(v1)
                        except:
                            v1 = 0.0
                        try:
                            in_time = int(vals[5])
                        except:
                            pass
                        else:
                            self.__data[in_time] = (v0, v1)
        self.__times = self.__data.keys()
        self.__times.sort()
        print "Found %d data in %s, last_update is %s" % (len(self.__times), self.name, time.ctime(self.last_update))
        if sum_data:
            sum_data.feed_data(self.__data)
    def _repair(self, sum_data, file_h):
        last_date = "X"
        new_lines = []
        in_db = False
        for line in self.lines:
            new_line = line
            if line.lstrip().startswith("<database>"):
                in_db = True
                ref_dates, rep_dates = ({}, {})
            elif line.lstrip().startswith("</database>"):
                in_db = False
            else:
                if in_db:
                    vals = line.strip().split()
                    act_date = vals[1]
                    v0, v1 = (vals[8], vals[10])
                    act_secs = int(vals[5])
                    if v0.lower() == "nan" and v1.lower() == "nan":
                        # repair
                        v0, v1 = sum_data.get_num(act_secs)
                        vals[8], vals[10] = (str(v0), str(v1))
                        new_line = " ".join(vals)
                    elif act_secs < ref_time:
                        v0_n, v1_n = sum_data.get_num(act_secs)
                        vals[8], vals[10] = (str(v0_n), str(v1_n))
                        new_line = " ".join(vals)
                    if act_date != last_date:
                        print act_date
                        last_date = act_date
            file_h.write("%s\n" % (new_line))
        
def main():
    sum_dat = sum_data_obj()
    src_files = []
    max_entries = 0
    for entry in os.listdir(rra_dir):
        if entry.startswith("vix_iec_traffic_in_"):
            if entry != src_file:
                new_rrd = rrd_file("%s/%s" % (rra_dir, entry))
                if new_rrd.ok:
                    src_files.append(new_rrd)
                    new_rrd._parse(sum_dat)
                max_entries -= 1
                if not max_entries:
                    break
    dst_file = rrd_file("%s/%s" % (rra_dir, src_file))
    dst_file._parse(None)
    new_fh = file(dst_file_name, "w")
    dst_file._repair(sum_dat, new_fh)
    new_fh.close()
    t_com = "/opt/rrdtool/bin/rrdtool restore %s %s" % (dst_file_name, dst_file_rrd_name)
    print "Doing %s" % (t_com)
    print commands.getstatusoutput(t_com)
    

if __name__ == "__main__":
    main()
    
