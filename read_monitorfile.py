#!/usr/bin/python -Ot

import os
import os.path
import sys
import struct
import gzip
import time
import getopt
import cStringIO

def main():
    sys.path.append("/usr/local/share/home/local/development/host-monitoring/modules")
    import process_monitor_mod
    try:
        opts,args=getopt.getopt(sys.argv[1:],"f:p:")
    except:
        print "Commandline error"
        sys.exit(-1)
    filename=None
    pid=None
    for opt,arg in opts:
        if opt=="-f":
            filename=arg
        elif opt=="-p":
            pid=int(arg)
    if not filename:
        print "Need filename!"
        sys.exit(-1)
    pdict={}
    tag_dict={"TI":[0,"Ld"],"MI":[0,"II"],"LA":[0,"III"],"PS":[1,"IIIIIII"],"PR":[1,"IIIIIII"],"PM":[0,"IIIIIIII"],"PE":[0,"I"],"PU":[0,"Id"]}
    size_dict={}
    pad_dict={}
    #file=gzip.GzipFile(filename,"rb")
    file=open(filename,"r")
    isize=struct.calcsize("I")
    # determine logversion
    version=struct.unpack("I",file.read(4))[0]
    if version > 100:
        print "No Version information, assuming Version 0 or 1"
        file.close()
        file=gzip.GzipFile(filename,"rb")
    else:
        print "Version ",version
    tagf="2s"
    tagfs=struct.calcsize(tagf)
    # build extra dictioniaries
    for tag in tag_dict.keys():
        extra,packf=tag_dict[tag]
        size_dict[tag]=struct.calcsize(packf)
        pad_dict[tag]=struct.calcsize(tagf+packf)-struct.calcsize(packf)-tagfs
    nt=0
    np=0
    u_id=None
    while 1:
        fdata=file.read(4)
        if fdata:
            len=struct.unpack("L",fdata)[0]
        else:
            break
        gzbuff=gzip.GzipFile(mode="rb",fileobj=cStringIO.StringIO(file.read(int(len))))
        while 1:
            fdata=gzbuff.read(2)
            if fdata:
                tag=struct.unpack(tagf,fdata)[0]
            else:
                break
            nt+=1
            extra,packf=tag_dict[tag]
            if pad_dict[tag]:
                gzbuff.read(pad_dict[tag])
            data=struct.unpack(packf,gzbuff.read(size_dict[tag]))
            if extra:
                indat=gzbuff.read(data[1]+data[2])
                names=struct.unpack(str(data[1])+"s"+str(data[2])+"s",indat)
                #print "Tag:",tag,data,names
            else:
                #print "Tag:",tag,data
                pass
            #if tag in ["PS","PE"]:
            #print "tag=",tag
            if tag=="TI":
                tstr="Time: %s"%(time.ctime(data[1]))
            if tag=="PS":
                if tstr:
                    print tstr
                    tstr=None
                pdict[data[0]]=process_monitor_mod.process(pid=data[3],name=names[0])
                if pid==data[3]:
                    u_id=data[0]
                if u_id==data[0]:
                    print "New process, pid %d, uid %d, gid %d : %s, cmdline: %s"%(data[3],data[5],data[6],names[0],names[1])
            if tag=="PE":
                if tstr:
                    print tstr
                    tstr=None
                proc_s=pdict[data[0]]
                if u_id==data[0]:
                    print "Process %s (pid %d) ended"%(proc_s.name,proc_s.pid)
                del pdict[data[0]]
                if u_id:
                    if u_id==data[0]:
                        u_id=None
            else:
                if u_id==data[0]:
                    if tstr:
                        print tstr
                        tstr=None
                    print tag,data
        gzbuff.close()
    file.close()
    print "read %d tags"%(nt)
    
if __name__=="__main__":
    main()
