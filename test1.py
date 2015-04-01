#!/usr/bin/python -Ot

import RRDtool
import string
import sys
import time

def main():
    rrd=RRDtool.RRDtool()
    numval=64
    btime=60
    num_rrd=100
    val_a=["dummy"]
    val_a.append("-s "+str(btime))
    for i in range(numval):
        val_a.append("DS:v"+str(i)+":GAUGE:180:U:U")
    # tuples of (slot_length, max_time) in minutes
    rra_a=[(1,60*24),(5,60*24*7),(120,60*24*7*12)]
    for stime,ttime in rra_a:
        st_r=stime*60/btime
        tt_r=ttime*60/btime/(st_r)
        print stime,ttime,":",st_r,tt_r
        for rra_t in ["AVERAGE","MAX","MIN"]:
            val_a.append("RRA:"+rra_t+":0.5:"+str(st_r)+":"+str(tt_r))
    mft_list=[]
    for mftnum in range(num_rrd):
        mft_name="mft_"+str(mftnum)+".rrd"
        mft_list.append(mft_name)
        val_a[0]=mft_name
        rrd.create(tuple(val_a))
        print "generated "+mft_name
    num=0
    val=1
    while num < 100000:
        num+=1
        time.sleep(1)
        valstr="N"
        for i in range(numval):
            valstr+=":"+str(val)
            val+=1
        print num,time.ctime(time.time()),valstr
        for mft in mft_list:
            rrd.update((mft,valstr))
    sys.exit(0)
        
if __name__=="__main__":
    main()
    
