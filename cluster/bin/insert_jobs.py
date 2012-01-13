#!/usr/bin/python -Ot

import MySQLdb
import MySQLdb.cursors
import os
import os.path
import re
import stat
import sys
import string
import time
import getopt
import commands
import shutil

FLAGS_PENDING=1
FLAGS_DEL_REQ=2

def parse_list(str):
    rdict={}
    rlist=str.strip()
    if len(rlist):
        rlist=rlist.split(" ")
        for arg,val in [x.split("=",1) for x in rlist]:
            rdict[arg]=val
    return rdict

class job:
    def __init__(self,qtime,id):
        self.id=id
        self.qtime=qtime
        self.uid=self.qtime+"-"+str(self.id)
        # delete flag
        self.del_req=0
        # flags for database connection
        # index
        self.idx=0
        # job in database ? 
        self.in_db=0
        # job started ?
        self.started=0
        # job ended ?
        self.ended=0
        # num_starts
        self.num_starts=0
    def fill_start(self,rdict):
        str_f=["user","group","jobname","queue"]
        time_f=["ctime","etime","start"]
        rkeys=rdict.keys()
        for arg in str_f:
            if arg in rkeys:
                setattr(self,arg,rdict[arg])
        for arg in time_f:
            if arg in rkeys:
                setattr(self,arg,time.strftime("%Y%m%d%H%M%S",time.localtime(int(rdict[arg]))))
        if "exec_host" in rkeys:
            self.exec_host=rdict["exec_host"].split("+")
        if "Resource_List.nodect" in rkeys:
            self.nodect=int(rdict["Resource_List.nodect"])
        #print self.id
        for node in self.exec_host:
            if not node in jobnodes.keys():
                if mytc.execute("INSERT INTO jobnode VALUES(0,'"+node+"',NULL)"):
                    jobnodes[node]=mytc.insert_id()
        for le,act_d in [("user",jobusers),("group",jobgroups),("queue",jobqueues)]:
            val=getattr(self,le)
            if val:
                if val not in act_d.keys():
                    if mytc.execute("INSERT INTO job"+le+" VALUES(0,'"+val+"',NULL)"):
                        act_d[val]=mytc.insert_id()
    def fill_end(self,rdict):
        time_f=["end"]
        rkeys=rdict.keys()
        for arg in time_f:
            if arg in rkeys:
                setattr(self,arg,time.strftime("%Y%m%d%H%M%S",time.localtime(int(rdict[arg]))))
        if "Exit_status" in rkeys:
            self.exitstatus=int(rdict["Exit_status"])
        if "resources_used.walltime" in rkeys:
            val=[int(x) for x in rdict["resources_used.walltime"].split(":")]
            self.walltime=3600*val[0]+60*val[1]+val[2]
        for arg in ["mem","vmem"]:
            if "resources_used."+arg in rkeys:
                setattr(self,arg,int(rdict["resources_used."+arg][0:-2]))
        if "exec_host" in rkeys:
            self.exec_host=rdict["exec_host"].split("+")
        #print self.id
        if hasattr(self,"exec_host"):
            for node in self.exec_host:
                if not node in jobnodes.keys():
                    if mytc.execute("INSERT INTO jobnode VALUES(0,'"+node+"',NULL)"):
                        jobnodes[node]=mytc.insert_id()
    def del_request(self):
        self.del_req=1
    def sync_from_db(self,with_start=0):
        get_list=["job_idx","flags","num_starts","nodect"]
        if with_start:
            get_list.append("stime")
        mytc.execute("SELECT "+string.join(["j."+x for x in get_list],", ")+" FROM job j WHERE j.uid='"+str(self.uid)+"'")
        if mytc.rowcount == 0:
            self.in_db=0
        elif mytc.rowcount == 1:
            pjob=mytc.fetchone()
            self.idx=int(pjob["job_idx"])
            self.nodect=int(pjob["nodect"])
            self.in_db=1
            # the job must have been started (at least)
            self.started=1
            flags=int(pjob["flags"])
            if flags&FLAGS_PENDING==0:
                self.ended=1
            if flags&FLAGS_DEL_REQ:
                self.del_req=1
            self.num_starts=int(pjob["num_starts"])
            if "stime" in get_list:
                self.start=pjob["stime"]
            #print self.idx,self.nodect,self.in_db,self.started,self.ended
    def start_record(self,t_type=None):
        if t_type==1:
            self.started=1
        else:
            if self.started:
                #print "Error. Job with uid="+str(self.uid)+" already started (failed to start ?)."
                self.num_starts+=1
            else:
                self.num_starts=1
                self.started=1
    def insert(self):
        if not hasattr(self,"walltime"):
            if self.ended:
                print "  Error: Job with uid="+str(self.uid)+", end-tag had no info about the consumed resources, setting to null."
            if hasattr(self,"exec_host"):
                self.nodect=len(self.exec_host)
            else:
                self.nodect=0
            self.mem=0
            self.vmem=0
            self.walltime=0
            if not hasattr(self,"exitstatus"):
                self.exitstatus=-666
            if self.exitstatus is None:
                self.exitstatus=-666
        if not hasattr(self,"start"):
            self.start=0
        #if self.end is None:
        if not hasattr(self,"end"):
            self.end=self.start
        #print "Inserting job with uid "+self.uid
        # check if this job is already inserted, qtime and id is REALLY unique (unless the pbs-Server is totally screwed up)
        if self.in_db==0:
            # create entry
            val_string="'%s',%d,%d,'%s',%d,%d,%d,'%s','%s','%s',%d,%d,%d,%d,%d,%d,%d"%(self.uid,
                                                                                       (1-self.ended)*FLAGS_PENDING+self.del_req*FLAGS_DEL_REQ,
                                                                                       self.id,
                                                                                       MySQLdb.escape_string(self.jobname),
                                                                                       jobusers[self.user],jobgroups[self.group],jobqueues[self.queue],
                                                                                       self.qtime,self.start,self.end,
                                                                                       self.num_starts,self.nodect,int(self.walltime),self.nodect*int(self.walltime),
                                                                                       self.mem,self.vmem,self.exitstatus)
            try:
                mytc.execute("INSERT INTO job VALUES(0,"+val_string+",NULL)")
            except:
                print "  Error: while inserting sql_string *** "+val_string+" ***",sys.exc_info()[0]
                mytc.execute("DELETE FROM job WHERE id="+str(self.uid)+" AND qtime="+str(self.qtime))
                sys.exit(-1)
            else:
                self.idx=mytc.insert_id()
        else:
            sql_dict={"etime":"'"+str(self.end)+"'",
                      "walltime":str(self.walltime),"twalltime":str(self.nodect*int(self.walltime)),
                      "mem":str(self.mem),"vmem":str(self.vmem),"exitstatus":str(self.exitstatus),
                      "num_starts":str(self.num_starts)}
##             sql_dict={"stime":"'"+str(self.start)+"'","etime":"'"+str(self.end)+"'","nodect":str(self.nodect),
##                       "walltime":str(self.walltime),"twalltime":str(self.nodect*int(self.walltime)),
##                       "mem":str(self.mem),"vmem":str(self.vmem),"exitstatus":str(self.exitstatus),
##                       "num_starts":str(self.num_starts)}
            #sql_dict["name"]="'"+MySQLdb.escape_string(self.jobname)+"'"
            #sql_dict["jobuser"]=str(jobusers[self.user])
            #sql_dict["jobgroup"]=str(jobgroups[self.group])
            #sql_dict["jobqueue"]=str(jobqueues[self.queue])
            sql_dict["flags"]=str((1-self.ended)*FLAGS_PENDING+self.del_req*FLAGS_DEL_REQ)

            sql_array=[]
            for k in sql_dict.keys():
                sql_array.append(k+"="+sql_dict[k])
            sql_string=string.join(sql_array,",")
            try:
                mytc.execute("UPDATE job SET "+sql_string+" WHERE uid='"+str(self.uid)+"'")
            except:
                print "  Error: while inserting sql_string *** "+sql_string+" ***"
                mytc.execute("DELETE FROM job WHERE id="+str(self.uid)+" AND qtime="+str(self.qtime))
                sys.exit(-1)
        # delete any job-node connections present
        mytc.execute("DELETE FROM jobnodecon WHERE job="+str(self.idx))
        if hasattr(self,"exec_host"):
            for node in self.exec_host:
                mytc.execute("INSERT INTO jobnodecon VALUES(0,"+str(self.idx)+","+str(jobnodes[node])+",NULL)")
        #print "Wrote "+str(self.uid)+" to db"
    def stop_record(self,info=None):
        success=1
        if not self.started:
            success=0
            print "Error. Job with uid="+str(self.uid)+" has not started."
            #if info:
            #    print info
            print "will pass now..."
            #sys.exit(-1)
        if self.ended:
            success=0
            print "Error. Job with uid="+str(self.uid)+" already ended"
            #if info:
            #    print info
            print "will pass now..."
            #sys.exit(-1)
        self.ended=1
        return success
    def __repr__(self):
        return self.uid
    
def main():
    global jobusers,jobgroups,jobqueues,jobnodes,mytc
    sys.path.append("/usr/local/python-modules")
    import configfile
    csuc,cfile=configfile.readconfig("/usr/local/mysql/etc/mysql.cf",1)
    if not csuc:
        csuc,cfile=configfile.readconfig("/usr/local/cluster/etc/cluster.cf",1)
    try:
        opts,args=getopt.getopt(sys.argv[1:],"f:hs:a:",["help"])
    except:
        print "Commandline error !"
        sys.exit(2)

    db=MySQLdb.connect(cfile["MYSQL_HOST"],user=cfile["MYSQL_USER"],passwd=cfile["MYSQL_PASSWD"],db=cfile["MYSQL_DATABASE"])
    mync=MySQLdb.cursors.DictCursor(db)
    mytc=MySQLdb.cursors.DictCursor(db)

    # dictionary of nodes
    jobnodes={}
    mync.execute("SELECT j.jobnode_idx,j.name FROM jobnode j")
    for ju in mync.fetchall():
        jobnodes[ju["name"]]=ju["jobnode_idx"]
    # sync with jobuser/jobgroup/jobqueue
    jobusers={}
    jobgroups={}
    jobqueues={}
    mync.execute("SELECT j.jobuser_idx,j.name FROM jobuser j")
    for ju in mync.fetchall():
        jobusers[ju["name"]]=ju["jobuser_idx"]
    mync.execute("SELECT j.jobgroup_idx,j.name FROM jobgroup j")
    for ju in mync.fetchall():
        jobgroups[ju["name"]]=ju["jobgroup_idx"]
    mync.execute("SELECT j.jobqueue_idx,j.name FROM jobqueue j")
    for ju in mync.fetchall():
        jobqueues[ju["name"]]=ju["jobqueue_idx"]
    
    localaccdir="/usr/local/mysql/accounting"

    read_file=localaccdir+"/.read"
    p_dead_file=localaccdir+"/.possibly_dead"
    r_dead_file=localaccdir+"/.really_dead"

    accdir="/var/spool/pbs/server_priv/accounting"
    server="LOCAL"
    for opt,arg in opts:
        if opt in ("-h","--help"):
            print "Help!"
            sys.exit(1)
        if opt=="-s":
            server=arg
        if opt=="-a":
            accdir=arg

    if server=="LOCAL":
        print "local files..."
        (cstat,out)=commands.getstatusoutput("ls -l %s"%(accdir))
    else:
        print "Syncing with server %s, accouting directory %s ."%(server,accdir)
        (cstat,out)=commands.getstatusoutput("ssh %s ls -l %s"%(server,accdir))
    if cstat:
        print "Unable to sync: %s, %s"%(cstat,out)
        sys.exit(-1)
    fls=string.split(out,"\n")
    tfilelist=[]
    for fl in fls:
        rm=re.match("^\S+\s+[0-9]+(\s+root){2,2}\s+([0-9]+)(\s+\S+){3,3}\s+(.*)$",fl)
        if rm:
            sfile=rm.group(4)
            resync=1
            localfile="%s/%s"%(localaccdir,sfile)
            if os.path.exists(localfile):
                if os.path.isfile(localfile):
                    ssize=int(rm.group(2))
                    lsize=os.stat(localfile)[stat.ST_SIZE]
                    if ssize == lsize:
                        resync=0
            if resync:
                print "Syncing file %s"%(sfile)
                if server=="LOCAL":
                    shutil.copyfile("%s/%s"%(accdir,sfile),localaccdir+"/"+sfile)
                else:
                    (cstat,out)=commands.getstatusoutput("scp root@%s:%s/%s %s"%(server,accdir,sfile,localfile))
                    if cstat:
                        print "Unable to copy : %s, %s"%(cstat,out)
            if os.path.exists(localfile):
                lsize=os.stat(localfile)[stat.ST_SIZE]
                if lsize:
                    tfilelist.append(os.path.basename(localfile))

    rf_dict={}
    try:
        rfile=open(read_file,"r")
        for line in [x.strip().split(" ") for x in rfile.readlines()]:
            if len(line)==2:
                rf_dict[line[0]]=(int(line[1]),0)
            else:
                rf_dict[line[0]]=(int(line[1]),int(line[2]))
        rfile.close()
    except:
        pass

    job_queue_only_dict={}
    job_dict={}
    job_id_dict={}
    for tfile in tfilelist:
        #if tfile=="20011201": break
        if not rf_dict.has_key(tfile):
            rf_dict[tfile]=(0,0)
        lines_read,size_read=rf_dict[tfile]
        file="%s/%s"%(localaccdir,tfile)
        fsize=os.path.getsize(file)
        try:
            cfile=open(file,"r")
        except:
            print "Can´t access file %s"%(file)
            sys.exit(2)
        outstr="Actual file %s, size %7d bytes, "%(tfile,fsize)
        exit=0
        if fsize != size_read:
            exit=1
            stime=time.time()
            num_ins=0
            lnum=0
            lproc=0
            for cs in [x.strip().split(";") for x in cfile.readlines()]:
                lnum+=1
                if len(cs) > 1 and lnum > lines_read:
                    a_type=cs[1]
                    lproc+=1
                    if a_type in ["S","E","D","T","Q"]:
                        ignore=0
                        date=cs[0]
                        id=int(cs[2].split(".")[0])
                        resdict=parse_list(cs[3])
                        if resdict.has_key("qtime"):
                            j_time=time.strftime("%Y%m%d%H%M%S",time.localtime(int(resdict["qtime"])))
                        else:
                            if a_type=="Q":
                                #generate qtime from string
                                j_time=time.strftime("%Y%m%d%H%M%S",time.strptime(date,"%m/%d/%Y %H:%M:%S"))
                                if not job_queue_only_dict.has_key(id):
                                    job_queue_only_dict[id]=j_time
                                ignore=1
                            else:
                                j_time="???"
                        if j_time=="???":
                            if job_id_dict.has_key(id):
                                j_time=job_id_dict[id].qtime
                            else:
                                mync.execute("SELECT j.id,j.uid,j.qtime FROM job j WHERE j.id="+str(id)+" ORDER BY j.job_idx DESC")
                                if mync.rowcount==0:
                                    ignore=1
                                    if job_queue_only_dict.has_key(id):
                                        pass
                                    else:
                                        print a_type,id,j_time,"???"
                                        print job_id_dict.keys()
                                else:
                                    j_time=mync.fetchone()["uid"].split("-")[0]
                        if not ignore:
                            if job_queue_only_dict.has_key(id):
                                #print "Removing job with id "+str(id)+" from queued-only list"
                                del job_queue_only_dict[id]
                            newjob=job(j_time,id)
                            if job_dict.has_key(newjob.uid):
                                newjob=job_dict[newjob.uid]
                            else:
                                job_id_dict[newjob.id]=newjob
                                job_dict[newjob.uid]=newjob
                                newjob.sync_from_db()
                            #newjob=job_dict[jui]
                            if a_type in ["S","E"]:
                                if a_type=="S":
                                    newjob.fill_start(resdict)
                                    #print "S:",id
                                    newjob.start_record()
                                elif a_type=="E":
                                    newjob.fill_end(resdict)
                                    #print "E:",id
                                    if newjob.stop_record(cs[3]):
                                        # write to database
                                        newjob.insert()
                                        num_ins+=1
                                    del job_dict[newjob.uid]
                                    del newjob
                                #if a_type=="S" or a_type =="E":
                                    #print reslist
                                    #print newjob
                            elif a_type=="D":
                                # delete event
                                newjob.del_request()
                            elif a_type=="T":
                                print "Found type '"+a_type+"' in "+str(cs)
                                newjob.start_record(t_type=1)
                            elif a_type=="Q":
                                # we ignore queuing events (see above)
                                pass
                    else:
                        #print "***",a_type
                        pass
            rf_dict[tfile]=(lnum,fsize)
            etime=time.time()
            dtime=etime-stime
            if dtime and lproc:
                outstr+="processed %7d lines in %5.1f seconds (%9.2f lines/sec), "%(lproc,dtime,lproc/dtime)
            #print job_dict
            outstr+="inserted %5d jobs (%7.2f jobs/sec), "%(num_ins,num_ins/dtime)
            if len(job_dict.keys()):
                outstr+="still %5d jobs in list"%(len(job_dict.keys()))
            print outstr
        cfile.close()
        # write read-file
        rfile=open(read_file,"w")
        for fn in rf_dict.keys():
            num_l,f_size=rf_dict[fn]
            rfile.write("%s %d %d\n"%(fn,num_l,f_size))
        rfile.close()
        #if exit:
        #    break
    for juid in job_dict.keys():
        job_dict[juid].insert()
    del job_dict
    jobusers={}
    mync.execute("SELECT j.jobuser_idx,j.name FROM jobuser j")
    for ju in mync.fetchall():
        jobusers[ju["name"]]=ju["jobuser_idx"]
    status,out=commands.getstatusoutput("/usr/local/bin/showq")
    # handle really-dead jobs
    try:
        dead_f=open(r_dead_file,"r")
        r_dead_list=[long(x.strip()) for x in dead_f.read().strip().split("\n")]
        dead_f.close()
    except:
        r_dead_list=[]
    for id in r_dead_list:
        print "id=",id
        mync.execute("SELECT j.id,j.uid,j.qtime FROM job j WHERE j.id="+str(id)+" AND (j.flags & 1) ORDER BY j.job_idx DESC")
        if mync.rowcount:
            job_info=mync.fetchone()
            print "Really dead job:",id,job_info.values()
            j_time=job_info["uid"].split("-")[0]
            del_job=job(j_time,id)
            del_job.sync_from_db(with_start=1)
            del_job.fill_end({})
            del_job.stop_record()
            del_job.insert()
            del del_job
    if status == 0:
        try:
            dead_f=open(p_dead_file,"r")
            old_dead_list=[long(x.strip()) for x in dead_f.read().strip().split("\n")]
            dead_f.close()
        except:
            old_dead_list=[]
        # open jobs in database
        db_open_jobs={}
        db_open_ids=[]
        # open jobs in jobsystem
        js_open_ids=[]
        mync.execute("SELECT j.id,j.flags FROM job j WHERE (flags & 1) ORDER BY id")
        for jinfo in mync.fetchall():
            db_open_ids.append(jinfo["id"])
            db_open_jobs[jinfo["id"]]=jinfo["flags"]
        sline_m=re.compile("^\s+(?P<id>\d+)\s+(?P<user>\S+)\s+(?P<state>\S+).*$")
        for line in out.split("\n"):
            slm=sline_m.match(line)
            if slm:
                if slm.group("user") in jobusers.keys():
                    js_open_ids.append(long(slm.group("id")))
        new_dead_list=[]
        for id in db_open_ids:
            if id not in js_open_ids:
                new_dead_list.append(id)
        r_dead_list=[]
        for id in new_dead_list:
            if id in old_dead_list:
                r_dead_list.append(id)
        try:
            dead_f=open(r_dead_file,"w")
            for entry in r_dead_list:
                dead_f.write("%d\n"%(entry))
            dead_f.close()
        except:
            pass
        try:
            dead_f=open(p_dead_file,"w")
            for entry in new_dead_list:
                dead_f.write("%d\n"%(entry))
            dead_f.close()
        except:
            pass
    else:
        print "Error calling showq",status
   
if __name__=="__main__":
    main()
    
