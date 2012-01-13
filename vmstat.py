#!/usr/bin/python -Ot

import os
import sys
import string
import time
import re

def main():
    lcpu=None
    lctxt=None
    ldisk_io=None
    lintr=None
    last_time=None
    while 1:
        try:
            sfile=open("/proc/stat")
            lines=sfile.read().split("\n")
            sfile.close()
        except:
            pass
        else:
            act_time=time.time()
            stat_dict={}
            for line in lines:
                lines=re.split("\s+",line.strip())
                if lines[0]=="cpu":
                    stat_dict["cpu"]=[int(x) for x in lines[1:]]
                elif lines[0]=="ctxt":
                    stat_dict["ctxt"]=int(lines[1])
                elif lines[0]=="intr":
                    stat_dict["intr"]=int(lines[1])
                elif lines[0]=="disk_io:":
                    #no_info=0
                    #read_io_ops=0
                    blks_read=0
                    #write_io_ops=0
                    blks_written=0
                    for io in [x.split(":")[1][1:-1].split(",") for x in lines[1:]]:
                        #no_info+=int(io[0])
                        #read_io_ops+=int(io[1])
                        blks_read+=int(io[2])
                        #write_io_ops+=int(io[3])
                        blks_written+=int(io[4])
                    #stat_dict["disk_io"]=[no_info,read_io_ops,blks_read,write_io_ops,blks_written]
                    stat_dict["disk_io"]=[blks_read,blks_written]
            stat_d={}
            if last_time:
                tdiff=act_time-last_time
            else:
                tdiff=None
            if stat_dict.has_key("ctxt"):
                if lctxt and tdiff:
                    stat_d["ctxt"]=int((stat_dict["ctxt"]-lctxt)/tdiff)
                lctxt=stat_dict["ctxt"]
            if stat_dict.has_key("cpu"):
                if lcpu:
                    idx=0
                    for i in ["user","nice","sys","idle"]:
                        stat_d[i]=float((stat_dict["cpu"][idx]-lcpu[idx])/tdiff)
                        idx+=1
                    #stat_d["user"]=100-(stat_d["nice"]+stat_d["sys"]+stat_d["idle"])
                lcpu=stat_dict["cpu"]
            if stat_dict.has_key("intr"):
                if lintr and tdiff:
                    stat_d["intr"]=int((stat_dict["intr"]-lintr)/tdiff)
                lintr=stat_dict["intr"]
            if stat_dict.has_key("disk_io"):
                if ldisk_io and tdiff:
                    idx=0
                    for i in ["blk_in","blk_out"]:
                        stat_d[i]=int((stat_dict["disk_io"][idx]-ldisk_io[idx])/tdiff)
                        idx+=1
                ldisk_io=stat_dict["disk_io"]
            last_time=act_time
            print stat_d
        time.sleep(1)
    
if __name__=="__main__":
    main()
