#!/usr/bin/python -Ot

import os
import os.path
import string
import sys
import gzip
import time
import getopt
import commands
import re

class monfile:
    name=""
    stime=""
    etime=""
    def __init__(self,name,stime=None,etime=None):
        self.name=name
        self.stime=stime
        self.etime=etime
def main():
    pdict={}
    hostname=sys.argv[1]#"Fri_Mar_15_14:28:49_2002.gz"
    dirname=sys.argv[2]
    comstr="./collclient.py --net --host %s pscom get_list"%(hostname)
    state,result=commands.getstatusoutput(comstr)
    if state:
        print "Command '%s' returned errorcode %d (%s)"%(comstr,state,result)
    else:
        lines=result.split("\n")
        linemm=re.compile("^File (?P<filename>\S+), from (?P<from>\S+) to (?P<to>\S+) .*$")
        mach_files=[]
        for line in lines:
            line_mo=linemm.search(line)
            if line_mo:
                f_str=line_mo.group("from")
                t_str=line_mo.group("to")
                #print line_mo.group("filename"),f_str,t_str
                mach_files.append(monfile(line_mo.group("filename"),f_str,t_str))
        local_files=[]
        loclist=os.listdir(dirname)
        loc_files=[]
        loc_names=[]
        entrym=re.compile("^(.*)\.gz$")
        for entry in loclist:
            mm=entrym.match(entry)
            if mm:
                name=mm.group(1)
                if name+".info" in loclist:
                    info=open(dirname+"/"+name+".info","r")
                    stime=None
                    etime=None
                    for line in info.readlines():
                        sline=line.strip().split("=")
                        if sline[0]=="START":
                            stime=sline[1]
                        elif sline[0]=="END":
                            etime=sline[1]
                    info.close()
                    if stime and etime:
                        loc_files.append(monfile(name,stime,etime))
                        loc_names.append(name)
        #sys.exit(0)
        #print "MACH  :",mach_files
        #print "LOCAL :",loc_files
        for mach_f in mach_files:
            act_name=mach_f.name
            if not act_name in loc_names:
                f_name=dirname+"/"+act_name+".gz"
                i_name=dirname+"/"+act_name+".info"
                print "Getting file ",act_name
                comstr="./collclient.py --net --host %s pscom -D %s get_file %s"%(hostname,dirname,act_name)
                state,result=commands.getstatusoutput(comstr)
                del_file=0
                if state:
                    print "Error retrieving file %s : %s"%(act_name,result)
                    del_file=1
                resp=result.split(" ")
                if resp[0]=="ok":
                    print result
                    comstr="./collclient.py --net --host %s pscom -D %s del_file %s"%(hostname,dirname,act_name)
                    state,result=commands.getstatusoutput(comstr)
                    print result
                else:
                    del_file=1
                #print len(resp),resp
                if del_file:
                    if os.path.isfile(f_name):
                        os.unlink(f_name)
                else:
                    new_info=open(i_name,"w")
                    new_info.write("START=%s\nEND=%s\n"%(mach_f.stime,mach_f.etime))
                    new_info.close()
if __name__=="__main__":
    main()
