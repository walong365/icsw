#!/usr/bin/python -Ot
import string
import getopt
import re
import sys
import os
import time

def main():
    try:
        opts,args=getopt.getopt(sys.argv[1:],"d:m:c:h")
    except:
        print "Commandline Error"
        sys.exit(-1)

    cdict={"cpu":None,"mb":None}
    numdel=0
    for opt,arg in opts:
        if opt=="-h":
            print "Usage: %s [ -h ] [ -c CPU-crit ] [ -m MB-crit ] [ -d num  ]"%(os.path.basename(sys.argv[0]))
            print "  where"
            print "  -c sets the value for the critical CPU-Temperature"
            print "  -m sets the value for the critical MB-Temperature"
            print "  -d sets the number of values to delete (upper and lower),"
            print "     however at least 6 values always remain in the list"
            sys.exit(0)
        if opt=="-c":
            try:
                cdict["cpu"]=float(arg)
            except:
                print "Error parsing critical CPU-Temp"
                sys.exit(-1)
        if opt=="-m":
            try:
                cdict["mb"]=float(arg)
            except:
                print "Error parsing critical MB-Temp"
                sys.exit(-1)
        if opt=="-d":
            try:
                numdel=int(arg)
            except:
                print "Error parsing number of values to be omitted"
                sys.exit(-1)


    logfile="/var/log/tmpwatch"
    logfile2="/tmp/tmpwatch"
    filen="/usr/local/netsaint/var/status.log"
    temp_hist={}

    wtemp_re=re.compile("^(.+)-temp.*$")
    temp_re=re.compile("^.*\s+(\d+\.*\d*)\s*°C.*$")
    statfield=["OK","WARNING","CRITICAL","RECOVERY"]

    def add(x,y): return x+y

    while 1:
        try:
            sfile=open(filen,"r")
        except:
            print "Can´t open file %s\n"%(filen)
            pass
        else:
            lines=sfile.read().split("\n")
            sfile.close()
            loctime=time.localtime()
            logfile_a=time.strftime("_%a_%d_%b_%Y",loctime)
            tdict={}
            for line in lines:
                cs=line.split(";")
                if len(cs) > 1:
                    fcs=cs[0].split(" ")
                    if fcs[1]=="SERVICE":
                        wtm=wtemp_re.match(cs[2].lower())
                        if wtm:
                            if cs[3] in statfield:
                                tf=temp_re.match(cs[24])
                                if tf:
                                    wtemp=wtm.group(1)
                                    try:
                                        temp=min(float(tf.group(1)),80.)
                                    except:
                                        pass
                                    else:
                                        if tdict.has_key(wtemp):
                                            tdict[wtemp].append(temp)
                                        else:
                                            tdict[wtemp]=[temp]

            secs=str(loctime[3]*3600+loctime[4]*60+loctime[5])
            for key in tdict.keys():
                try:
                    lfile=open(logfile+logfile_a+"."+key,"a")
                except:
                    lfile=open(logfile2+logfile+"."+key,"a")
                lfile.write("#Date: %s\n"%(time.ctime(time.time())))
                tdict[key].sort()
                tcount=len(tdict[key])
                if numdel:
                    tdel=numdel
                    while len(tdict[key]) >= 8 and tdel:
                        tdel-=1
                        del(tdict[key][0])
                        del(tdict[key][-1])
                tsum=reduce(add,tdict[key])
                tmax=max(tdict[key])
                tmin=min(tdict[key])
                tcount=len(tdict[key])
                if tcount:
                    tmid=tsum/tcount
                    acc=abs(1.-(tmax-tmin)/tmid)*100.
                    lfile.write("# %5s-temp (%3d): %5.2f (min), %5.2f (mean), %5.2f (max) ;  %5.2f %%\n"%(key.upper(),tcount,tmin,tmid,tmax,acc))
                    lfile.write("%s %d %5.2f %5.2f %5.2f %5.2f\n"%(secs,tcount,tmin,tmid,tmax,acc))
                    # insert tmid into history
                    if temp_hist.has_key(key):
                        if len(temp_hist[key]) > 10:
                            temp_hist[key].pop(0)
                    else:
                        temp_hist[key]=[]
                    temp_hist[key].append(tmid)
                else:
                    print "Error: no data for %s-temp !"%(key.upper())
                if temp_hist.has_key(key):
                    crit=cdict[key]
                    #lfile.write("#"+string.join([str(x) for x in temp_hist[key]]," ")+"\n")
                    if len(temp_hist[key]) > 2 and crit:
                        l0val=temp_hist[key][-1]
                        l1val=temp_hist[key][-2]
                        l2val=temp_hist[key][-3]
                        f01f=abs(1.-l0val/l1val)
                        f12f=abs(1.-l1val/l2val)
                        #lfile.write("#"+str(f01f)+" "+str(f12f)+"\n")
                        if l0val > crit and f01f < 0.2 and f12f < 0.2:
                            lfile.write("# Critical ! mean %s-temp is higher than critical value %5.2f\n"%(key.upper(),crit))
                            try:
                                sd_file=open("/.shutdown","w")
                            except:
                                pass
                            else:
                                sd_file.close()
            lfile.close()
        #break
        time.sleep(30)

if __name__=="__main__":
    main()
    
